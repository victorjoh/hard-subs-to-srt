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

    prev_hash = imagehash.hex_to_hash('0' * 256)
    subtitle_index = 1
    prev_subtitle = ""
    prev_change_millis = 0  # either the start or the end of a subtitle line

    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            cropped = frame[1600:2160, 820:3020]
            img = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            img = cv2.threshold(img, 250, 255, cv2.THRESH_BINARY)[1]
            above_subtitles = numpy.array(
                [[0, 0], [0, 46], [2200, 46], [2200, 0]])
            below_subtitles = numpy.array(
                [[0, 200], [0, 255], [2200, 255], [2200, 200]])
            # ensure white above and below text. Some blank space is needed for
            # tesseract
            img = cv2.fillPoly(
                img, pts=[above_subtitles, below_subtitles], color=0)
            img = cv2.bitwise_not(img)
            img = cv2.GaussianBlur(img, (21, 21), 0)
            img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)[1]
            cv2.imshow('Orignal cropped', cropped)
            cv2.imshow('Processed image for tesseract', img)

            textImage = Image.fromarray(img)
            hash = imagehash.average_hash(textImage, 32)
            # only use tesseract if the subtitle changes. This is for
            # performance and also to avoid having single frames of tesseract
            # mistakes that get entered into the srt file.
            if abs(prev_hash - hash) > 20:
                # Page segmentation mode (PSM) 13 means "Raw line. Treat the
                # image as a single text line, bypassing hacks that are
                # Tesseract-specific."
                text = pytesseract.image_to_string(
                    img, lang='chi_sim', config='--psm 13')
                text = text.replace("-", "一")
                text = text.replace("+", "十")
                text = text.replace("F", "上")
                text = text.replace("，", "")
                text = text.replace("。", "")
                text = text.replace("”", "")
                text = text.strip()

                if prev_subtitle != text:
                    if prev_subtitle != "":
                        line_start_time = millis_to_srt_timestamp(
                            prev_change_millis)
                        line_end_time = millis_to_srt_timestamp(
                            cap.get(cv2.CAP_PROP_POS_MSEC))
                        print(subtitle_index)
                        print(line_start_time + " --> " + line_end_time)
                        print(prev_subtitle)
                        print()
                        subtitle_index += 1
                    prev_subtitle = text
                    prev_change_millis = cap.get(cv2.CAP_PROP_POS_MSEC)

            prev_hash = hash

            # Press Q on keyboard to  exit
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break
            if cv2.waitKey(25) & 0xFF == ord('p'):
                while(True):
                    if cv2.waitKey(25) & 0xFF == ord('c'):
                        break

        # Break the loop
        else:
            break

    # When everything done, release the video capture object
    cap.release()

    # Closes all the frames
    cv2.destroyAllWindows()


def millis_to_srt_timestamp(total_millis):
    (total_seconds, millis) = divmod(total_millis, 1000)
    (total_minutes, seconds) = divmod(total_seconds, 60)
    (hours, minutes) = divmod(total_minutes, 60)
    return '{:02}:{:02}:{:02},{:03}'.format(int(hours), int(minutes), int(seconds), int(millis))
