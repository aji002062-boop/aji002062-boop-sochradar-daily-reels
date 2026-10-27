"""Official Meta Instagram publishing via Facebook Login / local resumable file upload.
Do not pass account passwords. Needs IG professional linked to Facebook Page and Page token.
"""
import os
import time
from pathlib import Path
from urllib.parse import urlparse
import requests

class PublishError(Exception): pass


def post_reel(movie,caption,state_callback=None):
    token=os.environ.get('IG_PAGE_ACCESS_TOKEN','').strip()
    igid=os.environ.get('IG_USER_ID','').strip()
    if not token or not igid: raise PublishError('Set IG_PAGE_ACCESS_TOKEN and IG_USER_ID secrets first.')
    api_version=os.environ.get('META_API_VERSION','v25.0')
    endpoint=f'https://graph.facebook.com/{api_version}/{igid}'
    video=Path(movie)
    session=requests.Session()
    container_req=session.post(f'{endpoint}/media',
        data={'media_type':'REELS','upload_type':'resumable','caption':caption,
              'share_to_feed':'true','thumb_offset':'0','access_token':token},timeout=35)
    container_req.raise_for_status()
    obj=container_req.json()
    container=obj.get('id');uri=obj.get('uri')
    if not container or not uri: raise PublishError('Missing container id/upload URL: '+str(obj))
    host=urlparse(uri)
    if host.scheme!='https' or host.hostname!='rupload.facebook.com':
        raise PublishError('Refusing unexpected upload hostname')
    if state_callback: state_callback('uploading',container)
    size=video.stat().st_size
    with video.open('rb') as fh:
        upload=session.post(uri,headers={'Authorization':f'OAuth {token}',
          'offset':'0','file_size':str(size),'Content-Type':'application/octet-stream'},
          data=fh,timeout=180)
    upload.raise_for_status()
    for _ in range(50):
        time.sleep(6)
        check=session.get(f'https://graph.facebook.com/{api_version}/{container}',
                          params={'fields':'status_code,status','access_token':token},timeout=25)
        check.raise_for_status()
        status=check.json().get('status_code','')
        if status=='FINISHED':break
        if status in ('ERROR','EXPIRED','PUBLISHED'):raise PublishError(f'Unexpected container state: {check.text[:250]}')
    else:raise PublishError('Media processing timed out; do not publish.')
    # IMPORTANT: if POST publish experiences a network timeout, blindly retrying can double-post.
    # Caller persists this intermediate state and requires manual reconciliation if uncertain.
    if state_callback:state_callback('publishing_pending',container)
    publish=session.post(f'{endpoint}/media_publish',data={'creation_id':container,'access_token':token},timeout=45)
    publish.raise_for_status()
    result=publish.json()
    media_id=result.get('id')
    if not media_id:raise PublishError('Publish returned no media id: '+str(result))
    return media_id
