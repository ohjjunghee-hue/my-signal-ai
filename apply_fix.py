#!/usr/bin/env python3
"""Safe, exact-match update for V48 UI and bounded deep-scan configuration."""
from pathlib import Path
import ast, shutil, sys

def patch(root):
    root=Path(root)
    html=root/'index.html'; server=root/'server.py'
    if not html.is_file() or not server.is_file():
        raise RuntimeError('index.html 및 server.py가 있는 저장소 폴더에서 실행하세요.')
    h=html.read_text(encoding='utf-8'); s=server.read_text(encoding='utf-8')
    old_title='V45 · OUTCOME VALIDATION'
    old_top="TOP=max(5,min(160,int(os.getenv('DEEP_MARKETS','80'))))"
    if h.count(old_title)!=1 or s.count(old_top)!=1:
        raise RuntimeError('예상한 원본 코드와 다릅니다. 변경 없이 중단합니다.')
    new_h=h.replace(old_title,'V48 · INTEGRATED')
    # Default stays 80 to avoid API overload; allow configured limit up to 500.
    new_s=s.replace(old_top,"TOP=max(5,min(500,int(os.getenv('DEEP_MARKETS','80'))))")
    ast.parse(new_s); compile(new_s,str(server),'exec')
    for p in (html,server):shutil.copy2(p,p.with_suffix(p.suffix+'.pre_v48_fix.bak'))
    html.write_text(new_h,encoding='utf-8'); server.write_text(new_s,encoding='utf-8')
    print('완료: UI V48 표시 / 심층분석 상한 설정 가능(기본 80 유지).')
    print('주의: 전체 심층분석 속도 및 API 안정성은 별도 운영 검증 필요.')

if __name__=='__main__':
    try:patch(sys.argv[1] if len(sys.argv)>1 else '.')
    except Exception as e:print('중단:',e,file=sys.stderr);sys.exit(1)
