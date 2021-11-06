# Hardcoded Subtitles to SRT
Creates an
[SRT](https://www.matroska.org/technical/subtitles.html#srt-subtitles) file from
a video file that has hardcoded subtitles. For example,

![Example subtitle](example.png)

will generate

```
57
00:03:20,200 --> 00:03:22,120
就是那涌泉村的几户
```

The script relies on [Tesseract](https://github.com/tesseract-ocr/tesseract) for
the optical character recognition.