from PIL import Image
import pytesseract
import imagehash
import time

def load_text_image(img_path):
    im = Image.open(img_path)
    cropped = im.crop((600, 1200, 2750, 1460))
    imgrey = cropped.convert('L')
    return imgrey.point(lambda value: 0 if value > 250 else 255)

onlytext1 = load_text_image('test1.png')
hash1 = imagehash.average_hash(onlytext1, 32)
print(hash1)

onlytext2 = load_text_image('test2.png')
onlytext2.show()
hash2 = imagehash.average_hash(onlytext2, 32)
print(hash2)

t0 = time.time()
onlytext3 = load_text_image('test3.png')
hash3 = imagehash.average_hash(onlytext3, 32)
t1 = time.time()
total = t1-t0
print(total)
print(hash3)

onlytext4 = load_text_image('test4.png')
onlytext4.show()
hash4 = imagehash.average_hash(onlytext4, 32)
print(hash4)

t0 = time.time()
text = pytesseract.image_to_string(onlytext2, lang='chi_sim')
t1 = time.time()
total = t1-t0
print(total)
print(text)

print(hash1 - hash2)
print(hash2 - hash3)
print(hash1 - hash4)
