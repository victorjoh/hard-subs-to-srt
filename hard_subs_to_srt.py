from os import times
from PIL import Image
import pytesseract
import imagehash
import cv2
import numpy
import sys
from imutils.video import FileVideoStream
from queue import Queue
from threading import Thread

NO_SUBTILE_FRAME_HASH = imagehash.hex_to_hash('0' * 256)


def extract_srt(video_file, srt_file):
    video = FileVideoStream(video_file)
    first_frame_pos = 2500
    video.stream.set(cv2.CAP_PROP_POS_FRAMES, first_frame_pos)

    if video.stream.isOpened() == False:
        print('Error opening video stream or file')
        return

    sys.stdout = FileAndTerminalStream(srt_file)
    convert_frames_to_srt(video, first_frame_pos)
    sys.stdout = sys.stdout.terminal

    cv2.destroyAllWindows()
    video.stop()


class FileAndTerminalStream(object):
    def __init__(self, file):
        self.terminal = sys.stdout
        self.srt = open(file, 'w', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.srt.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        pass


def convert_frames_to_srt(video, first_frame_pos):
    prev_frame_hash = NO_SUBTILE_FRAME_HASH
    frame_number = first_frame_pos
    reader = SubtitleReader()

    keyboard = Keyboard()

    width = video.stream.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = video.stream.get(cv2.CAP_PROP_FRAME_HEIGHT)
    preview_size = limit_size((width, height), (1280, 720))

    video.start()
    reader.start()

    while video.more():
        frame = video.read()
        cropped_frame = frame[1600:2160, 820:3020]
        monochrome_frame = to_monochrome_subtitle_frame(cropped_frame)
        cv2.imshow('Orignal', cv2.resize(frame, preview_size))
        cv2.imshow('Processed image for tesseract', monochrome_frame)

        textImage = Image.fromarray(monochrome_frame)
        frame_hash = imagehash.average_hash(textImage, 32)
        # only use tesseract if the subtitle changes. This is for  performance
        # and also to avoid having single frames of tesseract mistakes that get
        # entered into the srt file.
        if abs(prev_frame_hash - frame_hash) > 20:
            timestamp = get_millis_for_frame(video, frame_number)
            if frame_hash == NO_SUBTILE_FRAME_HASH:
                # no need to use tesseract when the input is a white rectangle
                change = EmptySubtitleChange(timestamp)
            else:
                change = SubtitleChange(monochrome_frame, timestamp)
            reader.provide_material(change)

        prev_frame_hash = frame_hash
        frame_number += 1

        keyboard.wait_key()
        # fps.update()
        if keyboard.last_pressed_key == ord('q'):
            return
        elif keyboard.last_pressed_key == ord('p'):
            while keyboard.wait_key() != ord('c'):
                if (keyboard.last_pressed_key == ord('q')):
                    return


class SubtitleReader:
    def __init__(self):
        self.changes = Queue(maxsize=128)
        self.thread = Thread(target=self.update, args=())
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def update(self):
        subtitle_index = 1
        prev_line = ""
        prev_change_millis = 0  # either the start or the end of a subtitle line

        while True:
            change = self.changes.get()
            line = change.read_subtitle()

            if prev_line != line:
                if prev_line != '':
                    print_line(
                        index=subtitle_index,
                        start_time=prev_change_millis,
                        end_time=change.timestamp,
                        text=prev_line)
                    subtitle_index += 1
                prev_line = line
                prev_change_millis = change.timestamp

    def provide_material(self, subtitle_change):
        self.changes.put(subtitle_change)


def print_line(index, start_time, end_time, text):
    line_start_time = millis_to_srt_timestamp(start_time)
    line_end_time = millis_to_srt_timestamp(end_time)
    print(index)
    print(line_start_time + ' --> ' + line_end_time)
    print(text)
    print()


class SubtitleChange:
    def __init__(self, frame, timestamp):
        self.frame = frame
        self.timestamp = timestamp

    def read_subtitle(self):
        # Page segmentation mode (PSM) 13 means "Raw line. Treat the image as a
        # single text line, bypassing hacks that are Tesseract-specific."
        line = pytesseract.image_to_string(
            self.frame, lang='chi_sim', config='--psm 13')
        return clean_up_tesseract_output(line)


class EmptySubtitleChange:
    def __init__(self, timestamp):
        self.timestamp = timestamp

    def read_subtitle(self):
        return ''


class Keyboard:
    last_pressed_key = 0

    def wait_key(self):
        self.last_pressed_key = cv2.waitKey(1)
        return self.last_pressed_key


def limit_size(size, max_dimensions):
    (width, height) = size
    (max_width, max_height) = max_dimensions

    if width <= max_width and height <= max_height:
        return size

    if width / height > max_width / max_height:
        return (max_width, int(height * max_width / width))
    else:
        return (int(width * max_height / height), max_height)


def to_monochrome_subtitle_frame(cropped_frame):
    # see https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html for more
    # information
    img = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
    # make the image monochrome where only the whitest pixel are kept white
    img = cv2.threshold(img, 250, 255, cv2.THRESH_BINARY)[1]
    above_subtitles = numpy.array([[0, 0], [0, 46], [2200, 46], [2200, 0]])
    below_subtitles = numpy.array(
        [[0, 200], [0, 255], [2200, 255], [2200, 200]])
    # ensure white above and below text. Some blank space is needed for tesseract
    img = cv2.fillPoly(img, pts=[above_subtitles, below_subtitles], color=0)
    img = cv2.bitwise_not(img)
    # Add some blur since some pixels within the subtitles are not completely
    # white. This also eliminates smaller groups of white pixels outside of the
    # subtitles
    img = cv2.GaussianBlur(img, (21, 21), 0)
    img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)[1]
    return img


def clean_up_tesseract_output(text):
    # clean up common mistakes made by tesseract
    text = text.replace('-', '一')
    text = text.replace('+', '十')
    text = text.replace('F', '上')
    text = text.replace('，', '')
    text = text.replace('。', '')
    text = text.replace('”', '')
    text = text.strip()
    return text


def millis_to_srt_timestamp(total_millis):
    (total_seconds, millis) = divmod(total_millis, 1000)
    (total_minutes, seconds) = divmod(total_seconds, 60)
    (hours, minutes) = divmod(total_minutes, 60)
    time_format = '{:02}:{:02}:{:02},{:03}'
    return time_format.format(int(hours), int(minutes), int(seconds), int(millis))


def get_millis_for_frame(video, frame_number):
    return 1000.0 * frame_number / video.stream.get(cv2.CAP_PROP_FPS)
