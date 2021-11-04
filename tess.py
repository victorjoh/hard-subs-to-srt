from PIL import Image
import pytesseract

img = Image.open('two-chars.png')
text = pytesseract.image_to_string(img, lang='chi_sim', config='--psm 13')
print(text)

img = Image.open('test.png')
text = pytesseract.image_to_string(img, lang='chi_sim', config='--psm 13')
print(text)

img = Image.open('tricky.png')
text = pytesseract.image_to_string(img, lang='chi_sim', config='--psm 13')
print(text)


img = Image.open('tricky2.png')
text = pytesseract.image_to_string(img, lang='chi_sim', config='--psm 13')
print(text)