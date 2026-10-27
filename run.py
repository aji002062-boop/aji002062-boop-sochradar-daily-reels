"""One Reel per India-local date, backups in Drive, official Meta publishing opt-in.
Never publishes demonstration content. Uses Drive backup as the cross-run dedup ledger.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from content import get_news,call_gemini,demo_idea,evergreen_idea
from render import render
from publish import post_reel

TZ=ZoneInfo('Asia/Kolkata')

def exec_cmd(args,allow_missing=False):
    r=subprocess.run(args,capture_output=True,text=True)
    if r.returncode and not allow_missing:
        raise RuntimeError('rclone error: '+r.stderr[-700:])
    return r

def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))

def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Generate mock DEMO, never post')
    parser.add_argument('--force',action='store_true',help='Only for local manual DEMO development; not a publishing override')
    a=parser.parse_args()
    dt=datetime.now(TZ)
    datestamp=dt.strftime('%Y-%m-%d')
    folder=Path('output')/dt.strftime('%Y')/dt.strftime('%m')/datestamp
    folder.mkdir(parents=True,exist_ok=True)
    statefile=folder/'status.json'
    remote=f'gdrive:SochRadarIndia/{dt:%Y}/{dt:%m}/{datestamp}'
    has_drive = os.environ.get('DRIVE_ENABLED','false').lower()=='true' and not a.demo
    live_enabled=os.environ.get('AUTO_PUBLISH','false').lower()=='true' and not a.demo
    # If the GitHub runner is new, restore last stored MP4/state to avoid duplicates.
    if has_drive:
        exec_cmd(['rclone','copy',remote,str(folder),'--config',os.environ['RCLONE_CONFIG_FILE'],'--quiet'],allow_missing=True)
    state=read_json(statefile) if statefile.exists() else {}
    if state.get('status')=='posted' and not a.demo:
        print('Already posted for this Indian date:',datestamp, state.get('ig_media_id'))
        return
    if state.get('status')=='publishing_pending' and not a.demo:
        raise RuntimeError('Prior publish may have succeeded. Check Instagram before manual retry; duplicate post protected.')
    if a.demo or not (folder/'reel.mp4').exists():
        if a.demo:
            idea=demo_idea()
        else:
            try:
                news=get_news()
                idea=call_gemini(news,datestamp)
            except Exception as exc:
                print("Fresh-news generation unavailable; using clearly labeled evergreen EDUCATIONAL topic instead:",type(exc).__name__,str(exc)[:100])
                idea=evergreen_idea(dt.date())
        movie=render(folder,idea,dt.strftime('%d %b %Y'),demo=a.demo)
        caption=(idea['caption'].strip()+'\n\n'+' '.join(idea['hashtags']))[:2100]
        (folder/'post_caption.txt').write_text(caption,encoding='utf8')
        (folder/'source_links.txt').write_text('\n'.join(idea.get('source_urls',[])),encoding='utf8')
        write_json(folder/'content.json',idea)
        state={'status':'ready','date':datestamp,'created_at_ist':dt.isoformat(),
               'music':'Original synth generated locally, not a licensed trending song',
               'demo':bool(a.demo)}
        write_json(statefile,state)
    if a.demo:
        print('DEMO only. No Drive upload, no Instagram publish.')
        return
    if not has_drive:
        raise RuntimeError('DRIVE_ENABLED must be true for scheduled runs (persistent date-wise dedup). Generated assets are available as workflow artifact.')
    def backup():
        exec_cmd(['rclone','copy',str(folder),remote,'--config',os.environ['RCLONE_CONFIG_FILE'],'--quiet'])
        print('Backed up:',remote)
    # backup before publishing so media and caption are saved even if Meta fails
    backup()
    if not live_enabled:
        print('DRIVE BACKUP DONE. Instagram posting disabled until AUTO_PUBLISH=true.')
        return
    if state['status'] not in ('ready','uploading'):
        raise RuntimeError('Unknown/pending publishing state. Manually reconcile in Drive before retry.')
    def persist(status,container):
        state.update(status=status,ig_container_id=container)
        write_json(statefile,state)
        backup()
    media_id=post_reel(folder/'reel.mp4',(folder/'post_caption.txt').read_text(encoding='utf8'),persist)
    state.update(status='posted',ig_media_id=media_id,posted_at_ist=datetime.now(TZ).isoformat())
    write_json(statefile,state)
    backup()
    print('INSTAGRAM PUBLISHED. Media ID:',media_id)

if __name__=='__main__':main()
