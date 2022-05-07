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
import argparse

FIRST_FRAME = 2500 # Skip frames up to this point
PREVIEW_MAX_SIZE = (1280, 720)

# The subtitles are within these bounds. The bounds are not super tight since
# Tesseract works better with some blank space around the text.
SUBTITLE_BOUNDS_LEFT = 820
SUBTITLE_BOUNDS_RIGHT = 3020
SUBTITLE_BOUNDS_TOP = 1600
SUBTITLE_BOUNDS_BOTTOM = 1863
# We force some space above and below the subtitles to be white before feeding
# the text images to Tesseract.
SUBTITLE_BLANK_SPACE_ABOVE = 46
SUBTITLE_BLANK_SPACE_BELOW = 63

# Hardcoded subtitles are not entirely white. To filter out subtitles we look
# for pixels that are as bright or brighter than this. Completely white is 255
SUBTITLES_MIN_VALUE = 250
# We add some blur to the subtitle images before feeding them to Tesseract since
# some pixels within the subtitles are not white enough. This also eliminates
# smaller groups of white pixels outside of the subtitles. A bigger value means
# more blur.
SUBTITLE_IMAGE_BLUR_SIZE = (21, 21)
# After blurring the image we make the image monochrome since that works better
# for Tesseract. This is the limit for what should be considered a (white)
# subtitle pixel after the blur.
SUBTITLES_MIN_VALUE_AFTER_BLUR = 55

# Only use Tesseract if the subtitle changes. This is for performance and also
# to avoid having single frames of Tesseract mistakes that get entered into the
# SRT file. To tell if two images are of the same subtitle we compare the image
# hashes of them. See https://pypi.org/project/ImageHash/ for more information.
IMAGE_HASH_SIZE = 32
MAX_HASH_DIFFERENCE_FOR_SAME_SUBTITLE = 20
NO_SUBTILE_FRAME_HASH = imagehash.hex_to_hash('0' * 256)

TESSERACT_EXPECTED_LANGUAGE = 'chi_sim'
# Page segmentation mode (PSM) 13 means "Raw line. Treat the image as a single
# text line, bypassing hacks that are Tesseract-specific." See this link for
# other options:
# https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method
TESSERACT_CONFIG = '--psm 13'

# Tesseract makes mistakes. Some are easy to fix. Keys in this dictionary will
# be replaced with their respective values.
COMMON_MISTAKES = {
    '-': '一',
    '+': '十',
    'F': '上',
    '，': '',
    '。': '',
    '”': '',
}

OUTPUT_ENCODING = 'utf-8'


def main():
    parser = argparse.ArgumentParser(
        description='Creates an SRT file from a video file that has hardcoded subtitles')
    parser.add_argument(
        'video_file', help='the path to a video file that has hardcoded subtitles')
    parser.add_argument(
        'srt_file', help='where to put the resulting SRT file, will overwrite if it is already there')
    args = parser.parse_args()
    extract_srt(args.video_file, args.srt_file)


def extract_srt(video_file, srt_file):
    video = FileVideoStream(video_file)
    video.stream.set(cv2.CAP_PROP_POS_FRAMES, FIRST_FRAME)

    if video.stream.isOpened() == False:
        print('Error opening video stream or file')
        return

    sys.stdout = FileAndTerminalStream(srt_file)
    convert_frames_to_srt(video, FIRST_FRAME)
    sys.stdout = sys.stdout.terminal

    cv2.destroyAllWindows()
    video.stop()


class FileAndTerminalStream(object):
    def __init__(self, file):
        self.terminal = sys.stdout
        self.srt = open(file, 'w', encoding=OUTPUT_ENCODING)

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
    preview_size = limit_size((width, height), PREVIEW_MAX_SIZE)

    video.start()
    reader.start()

    frame = video.read()

    while frame is not None:
        cropped_frame = frame[SUBTITLE_BOUNDS_TOP:SUBTITLE_BOUNDS_BOTTOM,
                              SUBTITLE_BOUNDS_LEFT:SUBTITLE_BOUNDS_RIGHT]
        monochrome_frame = to_monochrome_subtitle_frame(cropped_frame)
        cv2.imshow('Orignal', cv2.resize(frame, preview_size))
        cv2.imshow('Processed image for tesseract', monochrome_frame)

        textImage = Image.fromarray(monochrome_frame)
        frame_hash = imagehash.average_hash(textImage, IMAGE_HASH_SIZE)
        # Only use Tesseract if the subtitle changes. This is for performance
        # and also to avoid having single frames of Tesseract mistakes that get
        # entered into the SRT file.
        hash_difference = abs(prev_frame_hash - frame_hash)
        if hash_difference > MAX_HASH_DIFFERENCE_FOR_SAME_SUBTITLE:
            timestamp = get_millis_for_frame(video, frame_number)
            if frame_hash == NO_SUBTILE_FRAME_HASH:
                # no need to use Tesseract when the input is a white rectangle
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

        frame = video.read()


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
        prev_change_millis = 0 # either the start or the end of a subtitle line

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
        line = pytesseract.image_to_string(self.frame,
            lang=TESSERACT_EXPECTED_LANGUAGE, config=TESSERACT_CONFIG)
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
    img = cv2.threshold(img, SUBTITLES_MIN_VALUE, 255, cv2.THRESH_BINARY)[1]

    bounds_width = SUBTITLE_BOUNDS_RIGHT - SUBTITLE_BOUNDS_LEFT
    bounds_height = SUBTITLE_BOUNDS_BOTTOM - SUBTITLE_BOUNDS_TOP
    whitespace_below_y = bounds_height - SUBTITLE_BLANK_SPACE_BELOW
    above_subtitles = numpy.array([[0, 0], [0, SUBTITLE_BLANK_SPACE_ABOVE],
        [bounds_width, SUBTITLE_BLANK_SPACE_ABOVE], [bounds_width, 0]])
    below_subtitles = numpy.array([[0, whitespace_below_y], [0, bounds_height],
    [bounds_width, bounds_height], [bounds_width, whitespace_below_y]])
    # ensure white above and below text. Some blank space is needed for
    # Tesseract
    img = cv2.fillPoly(img, pts=[above_subtitles, below_subtitles], color=0)

    # Add some blur since some pixels within the subtitles are not completely
    # white. This also eliminates smaller groups of white pixels outside of the
    # subtitles
    img = cv2.GaussianBlur(img, SUBTITLE_IMAGE_BLUR_SIZE, 0)
    img = cv2.threshold(
        img, SUBTITLES_MIN_VALUE_AFTER_BLUR, 255, cv2.THRESH_BINARY)[1]
    
    # Invert the colors to have white background with black text.
    img = cv2.bitwise_not(img)
    return img


def clean_up_tesseract_output(text):
    for key, value in COMMON_MISTAKES.items():
        text = text.replace(key, value)
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


if __name__ == "__main__":
    main()
