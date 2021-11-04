text = " ，那地方也不通班车"
text = text.replace("-", "一")
text = text.replace("+", "十")
text = text.replace("，", "");
text = text.replace("。", "");
text = text.replace("”", "");
text = text.strip();
print(text)