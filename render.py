"""Create Instagram-safe 720x1280 MP4 using Pillow, edge-tts/espeak and ffmpeg.
Graphic slides are original; no stock-video or song copyright dependency.
"""
import asyncio
import math
import os
import subprocess
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W,H=720,1280
DURATION=18.0
FONT_CANDIDATES = [
 '/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Bold.ttf',
 '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf',
 'C:/Windows/Fonts/NirmalaB.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]
FONT_REG = [
 '/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf',
 '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
 'C:/Windows/Fonts/Nirmala.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]


def font(size,bold=True,latin=False):
    if latin:
        for fn in (['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf'] if bold else ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf']):
            if Path(fn).exists(): return ImageFont.truetype(fn, size)
    for fn in (FONT_CANDIDATES if bold else FONT_REG):
        if Path(fn).exists(): return ImageFont.truetype(fn, size)
    return ImageFont.load_default()


def measure(draw,text,ft):
    return draw.textbbox((0,0),text,font=ft)[2]


def wrap(draw,text,ft,width,max_lines=4):
    words=str(text).replace('\n',' ').split()
    lines=[]; current=''
    for token in words:
        trial=f'{current} {token}'.strip()
        if measure(draw,trial,ft)<=width: current=trial
        else:
            if current: lines.append(current)
            current=token
    if current: lines.append(current)
    if len(lines)>max_lines: lines=lines[:max_lines]
    return lines


def write_lines(draw,text,ft,x,y,width,fill,space=19,max_lines=4):
    lines=wrap(draw,text,ft,width,max_lines)
    line_h=ft.size+space
    for ln in lines:
        draw.text((x,y),ln,font=ft,fill=fill,stroke_width=0)
        y+=line_h
    return y


def make_slide(out,index,scene,idea,date_label):
    image=Image.new('RGB',(W,H),(6,15,36))
    dr=ImageDraw.Draw(image)
    for y in range(H):
        q=y/H
        dr.line([(0,y),(W,y)], fill=(int(9+10*q),int(23+16*q),int(48+22*q)))
    # original stylized market wave art
    for p in range(3):
        points=[]
        for x in range(0,W+9,9):
            y=int(640 + 84*math.sin(x/90+p*0.7+index*0.75) + 45*math.sin(x/35 + p) + p*95)
            points.append((x,y))
        dr.line(points, fill= [(24,89,115),(25,145,155),(39,196,190)][p],width=4)
    for x in range(55,W,92):
        for y in range(255,1030,90): dr.ellipse((x,y,x+2,y+2),fill=(22,55,78))
    # brand header
    dr.rounded_rectangle((43,65,677,153),radius=21,fill=(13,32,59),outline=(36,82,104),width=2)
    dr.text((68,81),'SOCHRADAR',font=font(37,latin=True),fill=(249,252,254))
    dr.text((530,93),'INDIA',font=font(22,latin=True),fill=(57,226,207))
    dr.rounded_rectangle((45,192,335,248),radius=22,fill=(18,92,99))
    dr.text((66,200),'MARKET EXPLAINED',font=font(23,latin=True),fill=(213,255,245))
    dr.text((45,280),date_label,font=font(26,False,latin=True),fill=(170,204,221))
    # text card
    dr.rounded_rectangle((38,370,682,971),radius=38,fill=(15,32,54),outline=(29,106,115),width=3)
    dr.rectangle((60,404,68,499),fill=(50,234,209))
    headline=idea['hook'] if index==0 else scene['headline']
    top=write_lines(dr,headline,font(62),90,412,540,(255,205,75),space=19,max_lines=3)
    dr.line((88,top+30,628,top+30),fill=(56,108,123),width=2)
    body=scene.get('body','')
    write_lines(dr,body,font(39,False),90,top+65,530,(230,242,250),space=25,max_lines=5)
    if index==0:
        dr.rounded_rectangle((90,865,350,913),radius=15,fill=(18,109,125))
        dr.text((107,871),'15–20 SEC REEL',font=font(23,latin=True),fill=(227,249,247))
    # footer and progress
    dr.text((46,1040),'NEWS • LEARN • VERIFY',font=font(26,latin=True),fill=(137,211,216))
    dr.text((46,1113),'Education only · Not financial advice',font=font(21,False,latin=True),fill=(186,195,211))
    for i in range(4):
        dr.rounded_rectangle((46+i*160,1201,176+i*160,1213),radius=6,
                             fill=(48,222,196) if i<=index else (50,78,92))
    if idea.get('demo'):
        dr.rounded_rectangle((477,160,678,204),radius=13, fill=(149,66,29))
        dr.text((509,166),'DEMO ONLY',font=font(21,latin=True),fill=(255,246,233))
    image.save(out)


def create_music(path):
    import struct
    rate=16000
    chord=[164.81,196.0,246.94,293.66]
    with wave.open(str(path),'wb') as wf:
        wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(rate)
        for k in range(int(DURATION*rate)):
            t=k/rate
            beat=(t*105/60)%1
            pulse=math.exp(-8*beat)
            f=chord[int(t//4.5)%4]
            carrier=.6*math.sin(2*math.pi*f*t)+.22*math.sin(2*math.pi*f*2*t)
            shimmer=.15*math.sin(2*math.pi*(f*1.5)*t)
            gain=min(1,t/0.6,(DURATION-t)/0.9)
            val=int(3000*max(0,gain)*(0.26+0.30*pulse)*(carrier+shimmer))
            wf.writeframesraw(struct.pack('<h',max(-32768,min(32767,val))))


async def _tts(message,path):
    import edge_tts
    comm=edge_tts.Communicate(message, voice='hi-IN-SwaraNeural',rate='+12%')
    await comm.save(str(path))


def command(cmd):
    subprocess.run([str(p) for p in cmd],check=True,stdout=subprocess.DEVNULL)


def duration(path):
    p=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nokey=1:noprint_wrappers=1',str(path)])
    return float(p.strip())


def render(outdir,idea,date_label,demo=False):
    outdir=Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    scene_files=[]
    for i, scene in enumerate(idea['scenes']):
        image=outdir/f'card_{i+1}.png'
        make_slide(image,i,scene,idea,date_label)
        scene_files.append(image)
    music=outdir/'original_music.wav'
    create_music(music)
    voice=outdir/'hindi_voice.mp3'
    if not demo:
        try: asyncio.run(_tts(idea['voiceover'],voice))
        except Exception as e: raise RuntimeError(f'Hindi voice generation failed: {e}') from e
        voice_len=duration(voice)
        if voice_len>DURATION-0.3:
            # Keep important speech within the reel; slight tempo change, reject severe overflow
            speed=voice_len/(DURATION-.3)
            if speed>1.7: raise RuntimeError('Voiceover is far too long for an 18s reel; skip.')
        else: speed=1.0
    else:
        speed=1.0
    slideshow=outdir/'slides.txt'
    # Each image 4.5 seconds, concat demuxer requires final file entry too.
    slideshow.write_text(''.join(f"file '{p.name}'\nduration 4.5\n" for p in scene_files)+f"file '{scene_files[-1].name}'\n",encoding='utf-8')
    movie=outdir/'reel.mp4'
    video=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',slideshow,
           '-i',music]
    if not demo:
        video+=['-i',voice]
        audio_filter=f'[1:a]volume=0.18[m];[2:a]atempo={speed:.5f},apad,volume=1.65[v];[v][m]amix=inputs=2:duration=longest:dropout_transition=0,atrim=duration=18[a]'
    else:
        audio_filter='[1:a]volume=0.7,atrim=duration=18[a]'
    video+=['-filter_complex',audio_filter,'-map','0:v:0','-map','[a]',
            '-t',str(DURATION),'-r','30','-vf',"scale=750:1334,crop=720:1280:x='15+6*sin(t*1.2)':y='27+8*cos(t*0.7)',fps=30,format=yuv420p",
            '-c:v','libx264','-preset','veryfast','-crf','24','-c:a','aac','-ar','48000',
            '-b:a','128k','-movflags','+faststart',movie]
    command(video)
    print('Video rendered:', movie, '| seconds:',duration(movie))
    return movie
