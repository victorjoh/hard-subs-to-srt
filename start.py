from PIL import Image
import pytesseract
import imagehash
import time
import cv2
import numpy as np


def load_text_image(img_path):
    im = Image.open(img_path)
    cropped = im.crop((600, 1200, 2750, 1460))
    imgrey = cropped.convert('L')
    # turn white into black and grey and black into white
    return imgrey.point(lambda value: 0 if value > 254 else 255)


Video_FILE = '...'

cap = cv2.VideoCapture(Video_FILE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 5000)

if (cap.isOpened() == False):
    print("Error opening video stream or file")

prev_hash = imagehash.hex_to_hash('0' * 256)
while(cap.isOpened()):
    ret, frame = cap.read()
    if ret == True:

        cropped = frame[1600:2160, 820:3020]
        img = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        img = cv2.threshold(img, 250, 255, cv2.THRESH_BINARY)[1]
        above_subtitles = np.array([[0, 0], [0, 46], [2200, 46], [2200, 0]])
        below_subtitles = np.array([[0, 200], [0, 255], [2200, 255], [2200, 200]])
        # ensure white above and below text. Some blank space is needed for
        # tesseract
        img = cv2.fillPoly(img, pts =[above_subtitles, below_subtitles], color=0)
        img = cv2.bitwise_not(img)
        img = cv2.GaussianBlur(img, (21, 21), 0)
        img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)[1]
        cv2.imshow('Orignal cropped', cropped)
        cv2.imshow('Processed image for tesseract', img)

        textImage = Image.fromarray(img)
        hash = imagehash.average_hash(textImage, 32)
        if abs(prev_hash - hash) > 20:
            # Page segmentation mode (PSM) 13 means "Raw line. Treat the image
            # as a single text line, bypassing hacks that are
            # Tesseract-specific."
            text = pytesseract.image_to_string(img, lang='chi_sim', config='--psm 13')
            print(prev_hash - hash)
            text = text.replace("-", "一")
            text = text.replace("+", "十")
            text = text.replace("F", "上");
            text = text.replace("，", "");
            text = text.replace("。", "");
            text = text.replace("”", "");
            text = text.strip();
            print(text)
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
