from PIL import Image
import pytesseract
import imagehash
import cv2
import numpy


def extract_srt(video_file):
    cap = cv2.VideoCapture(video_file)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 5000)

    if (cap.isOpened() == False):
        print("Error opening video stream or file")

    convert_frames_to_srt(cap)

    cap.release()
    cv2.destroyAllWindows()


def convert_frames_to_srt(cap):
    prev_frame_hash = imagehash.hex_to_hash('0' * 256)
    subtitle_index = 1
    prev_line = ""
    prev_change_millis = 0  # either the start or the end of a subtitle line

    keyboard = Keyboard()

    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            cropped_frame = frame[1600:2160, 820:3020]
            monochrome_frame = to_monochrome_subtitle_frame(cropped_frame)
            cv2.imshow('Orignal cropped', cropped_frame)
            cv2.imshow('Processed image for tesseract', monochrome_frame)

            textImage = Image.fromarray(monochrome_frame)
            frame_hash = imagehash.average_hash(textImage, 32)
            # only use tesseract if the subtitle changes. This is for
            # performance and also to avoid having single frames of tesseract
            # mistakes that get entered into the srt file.
            if abs(prev_frame_hash - frame_hash) > 20:
                # Page segmentation mode (PSM) 13 means "Raw line. Treat the
                # image as a single text line, bypassing hacks that are
                # Tesseract-specific."
                line = pytesseract.image_to_string(
                    monochrome_frame, lang='chi_sim', config='--psm 13')
                line = clean_up_tesseract_output(line)

                if prev_line != line:
                    if prev_line != "":
                        line_start_time = millis_to_srt_timestamp(
                            prev_change_millis)
                        line_end_time = millis_to_srt_timestamp(
                            cap.get(cv2.CAP_PROP_POS_MSEC))
                        print(subtitle_index)
                        print(line_start_time + " --> " + line_end_time)
                        print(prev_line)
                        print()
                        subtitle_index += 1
                    prev_line = line
                    prev_change_millis = cap.get(cv2.CAP_PROP_POS_MSEC)

            prev_frame_hash = frame_hash

            keyboard.wait_key()
            if keyboard.last_pressed_key == ord('q'):
                return
            elif keyboard.last_pressed_key == ord('p'):
                while keyboard.wait_key() != ord('c'):
                    if (keyboard.last_pressed_key == ord('q')):
                        return

        else:
            return


class Keyboard:
    last_pressed_key = 0

    def wait_key(self):
        self.last_pressed_key = cv2.waitKey(1)
        return self.last_pressed_key


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
    text = text.replace("-", "一")
    text = text.replace("+", "十")
    text = text.replace("F", "上")
    text = text.replace("，", "")
    text = text.replace("。", "")
    text = text.replace("”", "")
    text = text.strip()
    return text


def millis_to_srt_timestamp(total_millis):
    (total_seconds, millis) = divmod(total_millis, 1000)
    (total_minutes, seconds) = divmod(total_seconds, 60)
    (hours, minutes) = divmod(total_minutes, 60)
    time_format = '{:02}:{:02}:{:02},{:03}'
    return time_format.format(int(hours), int(minutes), int(seconds), int(millis))
