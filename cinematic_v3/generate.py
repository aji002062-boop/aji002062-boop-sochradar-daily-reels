"""SochRadar V3 -- standalone, text-only daily cinematic brief generator.
Safeguards: never generates video, never posts to Instagram, never edits existing V1 assets.
"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
MASTER = (ROOT / 'master_prompt.txt').read_text(encoding='utf-8').split('\nINPUTS\n')[0]
BANK = json.loads((ROOT / 'topic_bank.json').read_text(encoding='utf-8'))


def model_candidates(key):
    forced = os.getenv('GEMINI_MODEL', '').strip().removeprefix('models/')
    if forced:
        return [forced]
    response = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                            headers={'x-goog-api-key': key}, params={'pageSize': 1000}, timeout=35)
    response.raise_for_status()
    available = [m['name'].removeprefix('models/') for m in response.json().get('models', [])
                 if 'generateContent' in m.get('supportedGenerationMethods', [])]
    preferred = ['gemini-3.1-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash',
                 'gemini-3-flash', 'gemini-2.0-flash']
    candidates = [x for x in preferred if x in available]
    candidates += [x for x in available if 'flash' in x and x not in candidates]
    if not candidates:
        raise RuntimeError('Gemini account has no available generateContent flash models. Check API key / free tier.')
    return candidates[:5]


def build_prompt(day, subject):
    user_prompt = f'''Create one original cinematic brief for SochRadar India on {day}.
Use this STYLE BIBLE exactly for the visual look (the wombat story is only a reference, NEVER the subject):\n{MASTER}\n
TODAY'S EDITORIAL SEED (must honor this seed; do not invent alternative facts):
{json.dumps(subject, ensure_ascii=False)}

Return a SINGLE compact JSON object with these keys:
category, topic, fact_check_notes, hook, script_clip1, script_clip2,
clip1, clip2, caption, hashtags, cover_text, original_audio_mood, instagram_music_search.
Each clip is an object with flow_prompt (standalone English 10-second CLEAN VIDEO PLATE prompt, visually detailed, 6-7 distinct shots, no baked text, include all style colors, aspect, hero object, lens, sound, continuity), power_word, beats.
Each beats array has 6 or 7 objects: start (number), end (number), world (one letter A-H), overlay_text (1-6 words, Hindi/Hinglish), camera_visual (short), sfx (short).
The first beat starts at 0, last ends at 10, and all adjacent beat boundaries match. Alternate worlds, never same consecutively. 3+ distinct worlds/clip. Make the final beat a clever memorable punchline. Voiceover 20 seconds TOTAL, approx 40-55 Hindi/Hinglish spoken words, split into 2 natural 10-second segments.
Content rules: cite no facts beyond supplied editorial seed. For factual story source is an unverified source suggestion; phrase accurately, no fake numbers. For fictional comedy treat as clearly fictional. No copyrighted character references, no unlicensed song request, no invented trending claim. New metaphors; never reuse wombat cube theme.
Output only valid JSON without markdown. Make both Flow prompts long enough to be standalone. For correct letters, NO generated readable text; overlay texts go in postproduction.
'''
    return user_prompt


def gemini_generate(prompt, key):
    failures = []
    for model in model_candidates(key):
        for attempt in range(2):
            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key': key}, timeout=120,
                json={'contents': [{'parts': [{'text': prompt}]}],
                      'generationConfig': {'responseMimeType': 'application/json',
                                           'temperature': .7, 'maxOutputTokens': 8192}})
            if not response.ok:
                failures.append(f'{model}: HTTP {response.status_code}')
                if response.status_code in (401, 403, 429):
                    raise RuntimeError('Gemini permission/rate limit problem: ' + failures[-1])
                break
            try:
                parts = response.json()['candidates'][0]['content']['parts']
                data = json.loads(''.join(p.get('text', '') for p in parts).strip())
                validate(data)
                return data, model
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                failures.append(f'{model} invalid JSON/beat timing: {str(exc)[:150]}')
                if attempt == 0:
                    prompt += '\nATTENTION: Prior JSON/beat validation failed. Correct time continuity and output complete JSON.'
                continue
    raise RuntimeError('Unable to make valid cinematic brief. ' + ' | '.join(failures[-5:]))


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('JSON must be object')
    for field in ('category','topic','hook','script_clip1','script_clip2','caption'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError('Missing ' + field)
    for c in ('clip1','clip2'):
        clip = data.get(c)
        if not isinstance(clip, dict) or len(clip.get('flow_prompt', '')) < 120:
            raise ValueError(c + ' needs independent detailed flow_prompt')
        beats = clip.get('beats', [])
        if len(beats) not in (6, 7):
            raise ValueError(c + ' must have 6 or 7 beats')
        expected = 0.0
        worlds = []
        for beat in beats:
            start, end = float(beat['start']), float(beat['end'])
            if abs(start - expected) > .08 or end <= start:
                raise ValueError(c + ' broken timestamps')
            expected = end
            world = str(beat.get('world','')).strip().upper()
            if world not in 'ABCDEFGH' or (worlds and world == worlds[-1]):
                raise ValueError(c + ' repeated/invalid world')
            worlds.append(world)
            if not isinstance(beat.get('overlay_text',''), str):
                raise ValueError('Missing overlay text')
        if abs(expected - 10) > .08 or len(set(worlds)) < 3:
            raise ValueError(c + ' not exactly 10 secs / insufficient scene diversity')
    return True


def write_files(out, data, subject, date, model, demo=False):
    out.mkdir(parents=True, exist_ok=True)
    for label, clipid in (('01_FLOW_PROMPT_CLIP_1.txt','clip1'), ('02_FLOW_PROMPT_CLIP_2.txt','clip2')):
        clip = data[clipid]
        (out / label).write_text(clip['flow_prompt'] + '\n', encoding='utf-8')
    (out / '03_HINDI_VOICE_SCRIPT.txt').write_text(
        f'CLIP 1 (0-10s):\n{data["script_clip1"]}\n\nCLIP 2 (10-20s):\n{data["script_clip2"]}\n', encoding='utf-8')
    overlays = []
    for index, cid in enumerate(('clip1','clip2')):
        overlays.append(f'=== CLIP {index+1} ===')
        for beat in data[cid]['beats']:
            overlays.append(f'{float(beat["start"]):.2f}-{float(beat["end"]):.2f}s | WORLD {beat["world"]} | {beat["overlay_text"]} | {beat.get("camera_visual","")} | SFX: {beat.get("sfx","")}')
    (out / '04_TEXT_SFX_TIMELINE.txt').write_text('\n'.join(overlays)+'\n', encoding='utf-8')
    hashtags = data.get('hashtags') if isinstance(data.get('hashtags'),list) else []
    hashtags = [str(x) for x in hashtags if re.fullmatch(r'#[\w]+', str(x))][:8]
    (out / '05_INSTAGRAM_CAPTION.txt').write_text(data['caption']+'\n\n'+' '.join(hashtags)+'\n\n@sochradarindia\n',encoding='utf-8')
    (out / '06_AUDIO_AND_COVER.txt').write_text(
        'COVER: '+str(data.get('cover_text',''))+'\nORIGINAL AUDIO: '+str(data.get('original_audio_mood',''))+
        '\nOPTIONAL MUSIC SEARCH (manual rights check): '+str(data.get('instagram_music_search',''))+'\n',encoding='utf-8')
    (out / '07_SOURCE_REVIEW.txt').write_text(
        f'TOPIC: {subject["topic"]}\nSEED FACT/COMEDY NOTE: {subject["fact"]}\nSOURCE SUGGESTION, VERIFY MANUALLY: {subject["source"] or "Fictional comedy, no source"}\n\nAI FACT CHECK NOTES:\n{data.get("fact_check_notes", "")}\n',
        encoding='utf-8')
    meta = {'date_ist':date,'generation':'OFFLINE DEMO (sample only)' if demo else 'Gemini prompt draft',
            'model':model,'topic':subject['topic'],'category':subject['category'],'video_generated':False,
            'instagram_published':False,'source_checked_by_human':False,'storyboard':data}
    (out / '08_STORYBOARD.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    (out / 'READ_ME_FIRST.txt').write_text('THIS FOLDER CONTAINS PROMPTS, NOT A VIDEO.\n1. Review fact and script.\n2. Generate TWO 10-second cinematic clean video plates in Google Flow manually.\n3. Add overlay text and voice in editing.\n4. Join and export 1080x1920 MP4.\n5. Upload/approve; AUTO_PUBLISH MUST STAY OFF until tested.\n',encoding='utf-8')


def sample():
    beats = []
    worlds = 'ABDEFGH'
    edges = [0,1.3,2.6,4.0,5.5,6.8,8.1,10.0]
    for i in range(7):
        beats.append({'start':edges[i], 'end':edges[i+1], 'world':worlds[i],
                      'overlay_text':['bhai','ek nahi','TEEN','dil','do gills','ek body','TRIPLE SHIFT!'][i],
                      'camera_visual':'cinematic photoreal object reveal and kinetic overlay in post',
                      'sfx':'soft whoosh / impact'})
    prompt = '10-second portrait 9:16, photoreal movie-quality clean plate, 7 rapid different worlds A black void, B white vignette, D gothic object, E macro craft, F test pattern, G dark diorama, H white fade. High contrast, clean negative space for titles, dramatic macro lens, moving glass hearts inspired by octopus biology, no text rendered in the plate. Original sound ambience, fast dramatic camera transitions, coherent two-clip palette. ' * 2
    return {'category':'Nature Fact','topic':'Octopus ke teen dil','hook':'TEEN DIL?',
            'script_clip1':'Bhai, octopus ke ek-do nahi, teen dil hote hain! Do dil khoon ko gills tak bhejte hain.',
            'script_clip2':'Aur teesra baaki body mein khoon pump karta hai. Matlab isne triple shift laga rakhi hai!',
            'clip1':{'flow_prompt':prompt,'power_word':'THREE','beats':beats},
            'clip2':{'flow_prompt':prompt,'power_word':'TRIPLE','beats':beats},
            'caption':'Octopus ke teen dil hote hain! Aapko ye fact pata tha?',
            'hashtags':['#SochRadarIndia','#OctopusFacts','#AmazingFacts'],
            'cover_text':'TEEN DIL?!','original_audio_mood':'playful dramatic original synth',
            'instagram_music_search':'cinematic quirky instrumental','fact_check_notes':'Demo example; verify source before sharing.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--demo', action='store_true', help='Offline sample, NOT an AI run, NO Drive upload')
    args = p.parse_args()
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    date = now.strftime('%Y-%m-%d')
    folder = OUTPUT / date
    subject = BANK[now.toordinal() % len(BANK)]
    if args.demo:
        subject = BANK[0]
        data = sample()
        validate(data)
        write_files(folder,data,subject,date,'OFFLINE DEMO',demo=True)
        print('Demo prompt pack generated; no model, video, Drive or Instagram was used:',folder)
        return
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing GEMINI_API_KEY repository secret')
    configfile = os.getenv('RCLONE_CONFIG_FILE', '').strip()
    if not configfile or not Path(configfile).is_file():
        raise RuntimeError('Missing Drive config. Confirm RCLONE_CONFIG_B64 secret and restored config file.')
    remote = f'gdrive:SochRadarCinematicV3/{now:%Y}/{now:%m}/{date}'
    old = subprocess.run(['rclone','lsf',remote,'--config',configfile],text=True,capture_output=True)
    if old.returncode == 0 and '08_STORYBOARD.json' in old.stdout:
        print('Already saved prompt package for this IST date. No duplicate. Remote:',remote)
        return
    if old.returncode and not any(x in old.stderr.lower() for x in ('directory not found','not found','does not exist')):
        raise RuntimeError('Google Drive connection failed. See rclone credentials/config; no upload attempted. '+old.stderr[-250:])
    data, model = gemini_generate(build_prompt(date, subject), key)
    validate(data)
    write_files(folder,data,subject,date,model)
    result = subprocess.run(['rclone','copy',str(folder),remote,'--config',configfile],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('Files were created locally but Drive upload failed. Check GitHub artifacts. '+result.stderr[-300:])
    print(f'SAVED PROMPTS (not video) to Google Drive: {remote} | Model: {model}')


if __name__ == '__main__':
    main()
