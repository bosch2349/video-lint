# tests/fixtures

E2E 테스트용 합성 영상. `generate.py`가 ffmpeg `lavfi` 소스(color/testsrc/sine/anullsrc)로 로컬 생성하며, 외부 다운로드는 없다.

생성된 `.mp4`는 git에 커밋하지 않는다 (바이너리라 diff가 안 되고, 재생성이 항상 가능하므로). `tests/test_e2e.py`가 필요할 때 자동으로 재생성한다. 수동으로 만들고 싶으면:

```
python3 tests/fixtures/generate.py
```

| fixture | 특징 | 기대 결과 |
|---|---|---|
| `sample.mp4` | 1080x1920, 검은화면 1초+testsrc 4초, 무음 | blackframes(시작) FAIL, loudness(너무 조용함) WARN |
| `still.mp4` | 3초 내내 완전 정지, 끝까지 회복 안 됨 | freeze FAIL |
| `still_then_motion.mp4` | 정지 2.5초 후 회복 | freeze WARN |
| `heavy_clip.mp4` | 검은화면 시작/끝 1초 + 과증폭 사인파(실제 클리핑) | blackframes FAIL, loudness 클리핑 WARN |
