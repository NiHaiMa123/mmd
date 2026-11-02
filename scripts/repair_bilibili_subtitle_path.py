"""Apply the two confirmed bilibili-agent fixes, guarded against unrelated edits."""
from pathlib import Path
ROOT=Path(r'E:\project\bilibili')


def replace(path,before,after):
    path=ROOT/path
    text=path.read_text(encoding='utf8')
    if text.count(before)!=1:raise RuntimeError('Patch context changed: '+str(path))
    path.write_text(text.replace(before,after),encoding='utf8')


replace(Path('src/bilibili_agent/pipeline.py'),
        'result = adapter.transcribe(wav_path, out_json=out_dir / "raw" / "asr.json")',
        'result = adapter.transcribe(wav, out_json=out_dir / "raw" / "asr.json")')
replace(Path('src/bilibili_agent/subtitle_resolver.py'),
        '    fallback: tuple[list[Segment], SubtitleTrack, str] | None = None',
        '    rejected_duration = False')
replace(Path('src/bilibili_agent/subtitle_resolver.py'),
        '        if duration_ms and span_ms > duration_ms * 1.5:',
        '        if duration_ms and max(span_ms, segments[-1].end_ms) > duration_ms * 1.5:')
replace(Path('src/bilibili_agent/subtitle_resolver.py'),
        '            if fallback is None:\n                fallback = (segments, track, body)',
        '            rejected_duration = True')
replace(Path('src/bilibili_agent/subtitle_resolver.py'),
        '    if fallback is not None:\n        segments, track, body = fallback\n        warnings.append("所有候选字幕的时长跨度都与视频时长不符，已采用最先取到的一条")\n        track.body = body\n        return segments, track, warnings',
        '    if rejected_duration:\n        warnings.append("没有时长匹配的字幕轨道；拒绝把疑似错配字幕当作视频内容")')
replace(Path('src/bilibili_agent/__init__.py'),'PIPELINE_VERSION = "0.1.0"','PIPELINE_VERSION = "0.1.1"')
test=ROOT/'tests/test_research_regressions.py'
if test.exists():raise RuntimeError('Regression file already exists')
test.write_text('''"""Actual research regressions: ASR default WAV and mismatched subtitle rejection."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from bilibili_agent.config import Config
from bilibili_agent.pipeline import Pipeline
from bilibili_agent.schemas import Segment
from bilibili_agent.subtitle_resolver import resolve_platform_subtitles


@pytest.mark.parametrize("explicit",[False,True])
def test_asr_receives_the_extracted_wav(tmp_path,monkeypatch,explicit):
    expected=tmp_path/'given.wav' if explicit else tmp_path/'part/raw/audio_16k.wav'
    class Adapter:
        def __init__(self,**kwargs):pass
        def diagnose(self):return []
        def extract_wav(self,media,out,**kwargs):
            assert Path(out)==expected
            Path(out).parent.mkdir(parents=True,exist_ok=True)
            Path(out).write_bytes(b'wave fixture')
        def transcribe(self,wav_path,**kwargs):
            assert Path(wav_path)==expected and Path(wav_path).is_file()
            return SimpleNamespace(ok=True,segments=[Segment(0,1000,'result')],warnings=[],meta={})
    monkeypatch.setattr('bilibili_agent.pipeline.ASRAdapter',Adapter)
    pipe=Pipeline(Config(root=tmp_path))
    try:
        segments,meta=pipe._get_asr_subtitles(tmp_path/'media.m4a',tmp_path/'part',[],
                                            wav_path=expected if explicit else None)
        assert segments[0].text=='result'
    finally:pipe.close()


@pytest.mark.parametrize('start,end',[(0,1346),(1000,1010)])
def test_only_mismatched_subtitles_are_not_returned_as_success(start,end):
    class Client:
        def get_json(self,*args,**kwargs):
            return {'data':{'subtitle':{'subtitles':[{'id':1,'lan':'ai-zh',
                'subtitle_url':'https://aisubtitle.hdslb.com/fixture.json','type':1}]}}}
        def get_text(self,*args,**kwargs):
            return json.dumps({'body':[{'from':start,'to':end,'content':'wrong video'}]})
    segments,track,warnings=resolve_platform_subtitles('BVfixture',1,Client(),duration_ms=304000,min_segments=1)
    assert segments==[] and track is None
    assert any('拒绝' in message for message in warnings)
''',encoding='utf8')
print('Patched ASR WAV input, duration rejection, cache version; added four regression cases.')
