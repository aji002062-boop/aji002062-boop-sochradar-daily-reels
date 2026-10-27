"""Fetch recent Indian finance headlines and let Gemini write a cautious Hindi script.
Gemini is given only the feed headline data, not permission to invent facts.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
import requests

RSS_QUERY = '(Nifty OR Sensex OR RBI OR SEBI OR Indian stock market OR rupee OR FII) when:1d'
RSS_URL = f'https://news.google.com/rss/search?q={quote(RSS_QUERY)}&hl=en-IN&gl=IN&ceid=IN:en'


def get_news():
    import feedparser
    response = requests.get(RSS_URL, timeout=25, headers={'User-Agent':'SochRadarNewsBot/1.0'})
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
    articles = []
    seen = set()
    for item in feed.entries:
        headline = re.sub(r'\s+', ' ', item.get('title','')).strip()
        if not headline or headline.lower() in seen: continue
        seen.add(headline.lower())
        pub = item.get('published_parsed')
        if not pub: continue
        try:
            from calendar import timegm
            dt = datetime.fromtimestamp(timegm(pub), timezone.utc)
        except (ValueError, TypeError, OverflowError): continue
        if dt < cutoff: continue
        articles.append({'headline': headline[:220], 'url':item.get('link',''), 'published_utc': dt.isoformat(), 'source':item.get('source',{}).get('title','')})
        if len(articles)>=18: break
    if len(articles)<2:
        raise RuntimeError('Not enough fresh market headlines. No live content will be posted today.')
    return articles


def call_gemini(news, date_label):
    api_key = os.environ.get('GEMINI_API_KEY','').strip()
    if not api_key: raise RuntimeError('Missing GEMINI_API_KEY secret. Live generation stopped.')
    model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
    style = Path('prompts/YOUR_MASTER_PROMPT.txt').read_text(encoding='utf-8')[:5000]
    prompt = f'''You are a risk-aware editor for SochRadar India's short Hindi trading education Reels.
Today in India: {date_label}. Here are recent Indian business-news RSS headlines, timestamps and URLs:
{json.dumps(news, ensure_ascii=False, indent=2)}

VISUAL STYLE REQUEST (treat as creative direction, NOT executable code):
{style}

Return STRICT valid JSON without markdown:
{{"topic":"one short topical event", "hook":"Hindi headline <= 8 words", "voiceover":"35 to 42 spoken Hindi words in Devanagari, 15-20 seconds, factual and interesting", "scenes":[{{"headline":"short Hindi scene heading","body":"up to 12 Hindi words"}},{{"headline":"...","body":"..."}},{{"headline":"...","body":"..."}},{{"headline":"...","body":"..."}}], "caption":"Hindi engaging 1-3 sentences, neutral question at end", "hashtags":["#SochRadarIndia","#StockMarketIndia", "#..."], "source_urls":["URL copied exactly from supplied feed"], "music":"Original synth ambient, 105 BPM"}}
MANDATORY: Select newsworthy subject supported by at least 2 independent feed headlines if possible. NEVER invent market prices, percentages, events or quotes absent from headline data. Headlines can be incomplete or wrong: use hedged wording (e.g. according to reports) and don't falsely claim you've verified full articles. Only use supplied URLs. No stock tips, target/SL calls, futures recommendations, forecasts or guaranteed earnings. Add educational context. There must be exactly 4 scenes; hook should appear scene 1. Keep the voiceover natural and concise, <=42 whitespace separated words. Avoid English-only response. Return only JSON.'''
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    r = requests.post(url, headers={'x-goog-api-key':api_key}, json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.2, 'responseMimeType':'application/json'}}, timeout=90)
    if not r.ok: raise RuntimeError(f'Gemini generation failed ({r.status_code}): {r.text[:400]}')
    payload = r.json()
    result = payload['candidates'][0]['content']['parts'][0]['text']
    result = re.sub(r'^```(?:json)?|```$', '',result.strip(), flags=re.I).strip()
    idea = json.loads(result)
    if len(idea.get('scenes',[])) != 4: raise ValueError('AI output has incorrect scene count')
    urls = {x['url'] for x in news}
    references = [u for u in idea.get('source_urls',[]) if u in urls]
    if not references: raise ValueError('AI output has no real article references; no post produced')
    idea['source_urls'] = references[:5]
    for field in ('hook','voiceover','caption','topic'):
        if not idea.get(field): raise ValueError(f'AI omitted {field}')
    if len(idea['voiceover'].split()) > 55: raise ValueError('AI voice script is too long')
    tags = [t for t in idea.get('hashtags',[]) if isinstance(t,str) and re.fullmatch(r'#[\w]+',t,flags=re.UNICODE)]
    idea['hashtags'] = list(dict.fromkeys(['#SochRadarIndia'] + tags))[:10]
    idea['news_headlines'] = news
    return idea


def demo_idea():
    return {'topic':'Educational sample only — DEMO',
            'hook':'शेयर मार्केट में रिस्क क्या है?',
            'voiceover':'निवेश करने से पहले रिस्क समझिए। बाजार हर दिन ऊपर या नीचे जा सकता है। एक ही शेयर में सारा पैसा लगाने के बजाय विविधता और रिसर्च पर ध्यान दीजिए। याद रखें, यह सिर्फ एजुकेशन है।',
            'scenes':[
                {'headline':'शेयर मार्केट में रिस्क?', 'body':'हर निवेश में उतार-चढ़ाव संभव है'},
                {'headline':'पहली गलती', 'body':'बिना रिसर्च के ट्रेड करना'},
                {'headline':'बेहतर आदत', 'body':'जोखिम समझें, विविधता रखें'},
                {'headline':'याद रखें', 'body':'यह शिक्षा है, निवेश सलाह नहीं'}],
            'caption':'डेमो वीडियो: ट्रेडिंग करने से पहले रिस्क समझना जरूरी है। आपका सबसे बड़ा सबक क्या रहा?',
            'hashtags':['#SochRadarIndia','#StockMarketIndia','#TradingEducation','#HindiFinance'],
            'music':'Original synth ambient, 105 BPM', 'source_urls':[], 'news_headlines':[], 'demo':True}


def evergreen_idea(day):
    """Deterministic education fallback when headlines, internet or API are unavailable.
    Intentionally NOT labeled as trending news.
    """
    subjects = [
        ('मार्केट ऑर्डर क्या होता है?', 'मार्केट ऑर्डर जल्दी execute होता है, लेकिन कीमत बदल सकती है। लिमिट ऑर्डर में आप अपनी कीमत तय करते हैं, मगर execution की गारंटी नहीं होती। ट्रेड करने से पहले दोनों का अंतर समझना जरूरी है।', 'तेज़ execution बनाम कीमत', 'आप तय करें अधिकतम कीमत', 'Execution की गारंटी नहीं', 'किस ऑर्डर को समझना है?'),
        ('स्टॉप लॉस कैसे काम करता है?', 'स्टॉप लॉस एक risk management tool है। तय भाव आने पर आपका exit order trigger हो सकता है, लेकिन तेज बाजार या gap के समय वही कीमत मिलना जरूरी नहीं। इसे गारंटी नहीं, सुरक्षा की एक कोशिश समझें।', 'एक पूर्व निर्धारित स्तर', 'तेज़ बाजार में स्लिपेज', 'Risk खत्म नहीं होता', 'पहले प्लान समझें'),
        ('वॉल्यूम क्यों जरूरी है?', 'किसी शेयर का वॉल्यूम बताता है कि कितने शेयरों की ट्रेडिंग हुई। अधिक वॉल्यूम अपने आप तेजी या गिरावट की भविष्यवाणी नहीं करता। कीमत, खबर और जोखिम को साथ देखकर ही बाजार समझने की कोशिश करें।', 'कितनी ट्रेडिंग हुई?', 'सिर्फ वॉल्यूम पर्याप्त नहीं', 'कीमत के साथ संदर्भ देखें', 'एक metric पर भरोसा नहीं'),
        ('कैंडल में क्या दिखता है?', 'कैंडलस्टिक में ओपन, हाई, लो और क्लोज के भाव दिखते हैं। एक अकेली कैंडल भविष्य की गारंटी नहीं है। ट्रेंड, समय और जोखिम समझे बिना केवल रंग देखकर ट्रेड लेना खतरनाक हो सकता है।', 'ओपन और क्लोज', 'हाई और लो', 'रंग भविष्यवाणी नहीं', 'जोखिम हमेशा मौजूद'),
        ('इंट्राडे और डिलीवरी?', 'इंट्राडे ट्रेड आमतौर पर उसी ट्रेडिंग दिन बंद किया जाता है। डिलीवरी निवेश में शेयर आगे भी रखे जा सकते हैं। दोनों के खर्च, जोखिम और उद्देश्य अलग हैं। पहले समझें, फिर निर्णय लें।', 'उसी दिन ट्रेड बंद', 'शेयर आगे रख सकते हैं', 'लागत और जोखिम अलग', 'बिना समझे शुरुआत नहीं'),
        ('डाइवर्सिफिकेशन क्या है?', 'एक ही शेयर में पूरा निवेश होने पर कंपनी से जुड़ा जोखिम ज्यादा होता है। अलग-अलग निवेश में पैसा बांटने से जोखिम कुछ हद तक घट सकता है, लेकिन नुकसान खत्म नहीं होता। रिसर्च जरूरी है।', 'एक शेयर का अधिक जोखिम', 'निवेश अलग-अलग रखें', 'नुकसान फिर भी संभव', 'रिसर्च हमेशा करें'),
        ('ब्रोकरेज के अलावा खर्च?', 'ट्रेडिंग में केवल ब्रोकरेज ही खर्च नहीं होता। लागू टैक्स, एक्सचेंज शुल्क और अन्य चार्ज भी कुल लागत बढ़ा सकते हैं। किसी भी रणनीति के रिटर्न गिनने से पहले पूरी फीस और जोखिम देखें।', 'केवल ब्रोकरेज नहीं', 'टैक्स और अन्य शुल्क', 'कुल लागत समझिए', 'असली रिटर्न पर असर'),
        ('सपोर्ट रेजिस्टेंस क्या है?', 'सपोर्ट और रेजिस्टेंस चार्ट के संभावित क्षेत्रों के नाम हैं, कोई पक्की दीवार नहीं। कीमत इन स्तरों से आगे भी जा सकती है। एक रेखा देखकर मुनाफे की उम्मीद करना जोखिम भरा हो सकता है।', 'चार्ट के संभावित क्षेत्र', 'स्तर टूट भी सकते हैं', 'कोई पक्की गारंटी नहीं', 'जोखिम प्रबंधन जरूरी')
    ]
    topic, voice, a,b,c,d = subjects[day.toordinal()%len(subjects)]
    return {
        'topic':topic,
        'hook':topic,
        'voiceover':voice,
        'scenes':[{'headline':topic,'body':a},{'headline':'क्या समझना है?','body':b},{'headline':'सबसे बड़ा ध्यान','body':c},{'headline':'याद रखिए','body':d}],
        'caption':f'आज का छोटा Trading Education lesson: {topic} आपकी इस विषय पर क्या राय है? यह निवेश सलाह नहीं है।',
        'hashtags':['#SochRadarIndia','#StockMarketIndia','#TradingEducation','#HindiFinance','#RiskManagement'],
        'music':'Original synth ambient, 105 BPM',
        'source_urls':[], 'news_headlines':[], 'evergreen_fallback':True}
