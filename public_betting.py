"""Read the public source page, without bypassing member gates or guessing shares."""
from html.parser import HTMLParser
from datetime import datetime,timezone
import re,urllib.request
URL='https://wiseguyteam.com/cbb-betting-splits?slate=full'
class PublicText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.hidden=max(0,self.hidden-1)
    def handle_data(self,text):
        if not self.hidden:self.parts.append(text)
def collect():
    result={'source':'Wise Guy Team','source_url':URL,'checked_at':datetime.now(timezone.utc).isoformat(),'records':[],
        'status':'unavailable','label':'Source check unavailable','reason':'Public source could not be read; no percentages inferred.'}
    try:
        request=urllib.request.Request(URL,headers={'User-Agent':'CBBResearch/1.0'})
        with urllib.request.urlopen(request,timeout=15) as response:page=response.read(2_000_000).decode('utf8')
        parser=PublicText();parser.feed(page);text=' '.join(parser.parts)
        if 'College Basketball' not in text:raise ValueError('Unexpected source page')
        future=re.search(r'feed lists\s+(\d+)\s+games outside',text,re.I)
        result.update(status='awaiting_reported_data',label='Wise Guy Team tracking linked',future_source_games=int(future[1]) if future else None,
            reason='The public server page does not expose verified per-game ticket/handle records. The interactive source board may have additional data; use its matchup link. Missing is not 0%.')
    except Exception:pass
    return result
