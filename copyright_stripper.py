import datetime
import json
import os
from pathlib import Path
from movie_render import MovieRenderer
from s3_wrapper import download_file, upload_file
from PIL import Image, ImageEnhance
from PIL import ImageFont
from PIL import ImageDraw, ImageFilter
from os import listdir
from os.path import isfile, join
# TODO: Windows machine.
#os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\bin"  # Adjust path to where you installed FFmpeg
print('start time')
print(datetime.datetime.now())
start_time = datetime.datetime.now()


def watermark_image(file_path: str, image_name: str, save_as_filename: str, watermark_text: str, save_path: str) -> None:
    """Download a single image.

    Args:
        url: URL to download the image from.
        file_path: Path to save the image to.
    """

    image = Image.open(file_path + "/" + image_name).convert("RGBA").rotate(angle=2.0, resample=Image.Resampling.BILINEAR, fillcolor="#FFF")
    txt = Image.new('RGBA', image.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt)
    w, h = image.size
    x, y = int(w / 2), int(h / 2)
    if x > y:
        font_size = y
    elif y > x:
        font_size = x
    else:
        font_size = x
    
    font = ImageFont.truetype("arial.ttf", int(font_size/12))
    transparency_value = 250
    draw.text((x + 75, y - 35), watermark_text, fill=(255, 255, 255, transparency_value), font=font, anchor='ms')
    draw.text((x - 100, y + 300), watermark_text, fill=(255, 255, 255, transparency_value), font=font, anchor='ms')
    draw.text((300, 100), watermark_text, fill=(255, 255, 255, transparency_value), font=font, anchor='ms')
    draw.text((w - 300, h - 100), watermark_text, fill=(255, 255, 255, transparency_value), font=font, anchor='ms')

    interference_text = ImageFont.truetype("arial.ttf", int(font_size/5))
    interference_transparency = 29
    for ny in range(100, h - 100):
        if ny % 285 != 0: # and y % 400 != 0 and y % 500 != 0
            continue
        draw.text((x - 15, ny), watermark_text, fill=(255, 255, 255, interference_transparency), font=interference_text, anchor='ms')
    for ny in range(100, h - 100):
        if ny % 400 != 0: # and y % 400 != 0 and y % 500 != 0
            continue
        draw.text((x + 75, ny), watermark_text, fill=(255, 255, 255, interference_transparency), font=interference_text, anchor='ms')
    
    combined_image = Image.alpha_composite(image, txt).convert('RGB')
    enhancer = ImageEnhance.Brightness(combined_image)
    brightened_image = enhancer.enhance(1.25)

    # Contrast
    enhancer = ImageEnhance.Contrast(brightened_image)
    contrasted_image = enhancer.enhance(1.15)

    # Color (Saturation)
    enhancer = ImageEnhance.Color(contrasted_image)
    colored_image = enhancer.enhance(1.2)
    enhancer = ImageEnhance.Sharpness(colored_image)
    sharpened_image = enhancer.enhance(1.8)
    sharpened_image.save(Path(save_path + "/" + save_as_filename))

    #thumbnail_size = 125, 125
    #combined_image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
    #combined_image.save(Path(save_path + "/thumb_" + save_as_filename + ".jpg"))


# S3 File test_video_05142025.mp4
# https://truevine-media-storage.s3.us-west-2.amazonaws.com/test_video_05142025.mp4
str_files_to_process = "31853915-7eb9-45c3-bedd-e1d91f65f62d.jpg,e8c006d1-c4e8-4371-8922-ec6e4913a77f.jpg,1153d792-af11-4547-b858-3b5bd2e0aec1.jpg,83b9aee9-0c87-430d-989d-0d40a09938f9.jpg,8c385cb2-2128-4432-81f0-aaff9846d15a.jpg,d537c785-0365-488b-b540-c86f0cc41c37.jpg,b6f18131-a724-486a-8b85-1b78063cb5df.jpg,37409082-c85a-46c3-8a25-0515f8d9486c.jpg,76ddcd93-391c-483b-9969-027938def23e.jpg,ad821ae2-3708-4baa-ac01-0d606b0777e9.jpg,bd680676-9fa3-4e09-98a6-03cdfea1acb4.jpg,bc6d7d04-496f-4c70-ae31-5c6a58809504.jpg,145d20a0-611a-43c1-9971-2113d00a5acb.jpg,87df7f66-7fd7-47c6-afc2-a56d5a73f603.jpg,195602fa-a811-457b-8865-2c41a27623aa.jpg,ae4fd282-8bf9-4545-a388-6b411a95602e.jpg,66aa6289-6d5c-4f26-96ea-8ec7978d53f1.jpg,e076b235-4320-405f-a8f9-ad991f52b060.jpg,498ea2c6-5f90-4cfe-9e84-581e32e1ab70.jpg,9ef40eb3-4a2e-4c55-b721-3f1615dc1d05.jpg,ba0cc251-36e4-4a5b-be9f-a35e6bfb095b.jpg,9d926b63-ba70-47e0-be82-c34231ef649f.jpg,7f33142a-565e-44a9-86f6-f59782e1ad87.jpg,44354423-a78b-4b92-ae97-ce0039e18f2f.jpg,7705ba45-9593-4399-a0f7-d9ca8a3a873d.jpg,087f22ad-8e27-4d27-b9ce-36f145b970b8.jpg,2589881c-6485-4c30-9f25-169314d74cad.jpg,a4f5ae81-2103-447e-ae0e-115d5f6f2eed.jpg,5d00128b-e72a-492a-bd14-6a7eae570b8b.jpg,5c1d31fd-79c0-4d79-bbf0-7559f03ff3bc.jpg,e79ec0e5-c802-45c6-a6ad-9f867bda1150.jpg,00b495d4-aa55-4445-bee0-012a5e9f58e4.jpg,bd7a2b41-45e4-45d0-9942-715ae3eacc77.jpg,bfff5a24-8b4c-4524-9577-56516b8ab24a.jpg,5dd6bb8a-700a-4724-bfca-9d0338a0b9ae.jpg,868c050d-0781-4d34-996d-6327a5e6a7b4.jpg,a6660cef-93f1-4cd7-889f-fa22aa169301.jpg,c6102a06-9d9a-45e0-8351-aa9d4abb396a.jpg,a31da803-3544-4c49-a146-3c700ea3bad3.jpg,7fb2b063-1fb2-46f4-80e2-62b2e70fd326.jpg,5371c0b0-ba59-41ba-9338-90fcf08fc434.jpg,58f32936-d8c5-4e64-ab5b-3c8208f85f12.jpg,382878e0-e0e1-4482-a3c4-4311cd926ac1.jpg,63205ee6-1345-4fff-bf3f-1368127b693e.jpg,13010a6d-41c0-4947-b955-744471cf5fbe.jpg,5b522408-536d-4f6e-868f-d4936120d8c4.jpg,8151daec-1029-41a2-81a0-afd8b60cc4d2.jpg,dd7b2dfb-4550-4eed-8338-edb631745f55.jpg,35ab70e2-b9cb-4ca0-babe-550843038bcf.jpg,8e849510-19b1-4383-a37c-18d0629e8c93.jpg,25f0002f-a4bc-4d82-b23a-22f2edfd5976.jpg,febf38a3-6c46-41d7-9c88-68bbf1bbba35.jpg,a48cc58a-e676-4693-8ff6-86f11a1ee4d3.jpg,d2dcda54-4052-44b8-abed-63785c40e16d.jpg,35187813-03d6-4a1b-b52b-69373978073c.jpg,6f8ea785-4c9d-4d1a-9f5f-d7b99309b887.jpg,fd8176b1-b018-4758-bef2-dc211473c0b7.jpg,294750b5-9bec-4a0a-aced-52c4f7c8ed5b.jpg,e3166f6d-5f01-4d8f-99c8-a0df5341df2b.jpg,ef90223b-bc8c-4cb7-b6fe-46587681ff22.jpg,73476af6-7573-4af1-bba0-19488524b726.jpg,39c289d5-26c9-4942-83c2-06f88b92756d.jpg,076920ff-b4b0-4e1d-acf6-3403fe8de9bd.jpg,6ee36a39-e0c5-41fa-a482-dcf28dc3dcc4.jpg,798628a6-fc6b-4f1d-a70b-a556786c02a8.jpg,24430522-9959-4df7-aff9-256247cb8dcb.jpg,f39b0f9f-6bf5-44cf-8152-dc724b732cee.jpg,5c669625-f322-46d7-ba8a-38ce29d42141.jpeg,0cf12c4c-85e8-42fa-a1df-c94ec6629c47.jpeg,3d3d16c7-1c5c-4f65-8794-59b301b205de.jpeg,5f099629-e6f8-4f8d-91b4-554dbbab1b8f.jpeg,d1536c70-e562-486f-9f0c-b164023d93a3.jpeg,576d62ed-92a8-4a7b-ba4f-809538c0536d.jpeg,0b4a4135-ffb5-431f-9f0e-c32d50a35a51.jpeg,c2c0a583-dd18-478e-bd72-20a2f1d8e193.jpeg,490f5202-8879-4eff-b2c0-f3141f5c1ce1.jpeg,629b0c9c-996b-43d1-b1a7-314a48abe1c3.jpeg,dbe8061c-1e47-40a9-b4b1-acaeef4dbb02.jpeg,fb65d6a8-9dfe-40ce-b543-313da0c5f4ca.jpeg,098ac485-6301-47db-ad4d-591d751858ae.jpeg,359354c5-1bc6-4353-a53d-1d5d17bc21a1.jpeg,ddf99552-35b0-49de-9139-fd2ef78b2e0a.jpeg,e612e70a-c96d-4df2-a063-0ee0cca5f0c3.jpeg,fedd58a9-41aa-472b-bbb7-95f505a1c160.jpeg,41c3d90c-70a1-4a10-8693-4c16e7628504.jpeg,6fb6b074-84fd-4574-a0ab-0fad3db4b32f.jpeg,d27d3f16-e436-4548-a387-e3a51e19ed03.jpeg,d492b1c7-69cf-4642-a5bc-8e7b47f9fe52.jpeg,bee937c7-4c87-4f37-b15f-9aeec6d3557d.jpeg,f09632ec-5ebf-4d3a-9636-5f7247bdbf22.jpeg,b6a25079-3b95-40f6-b395-70c42b947d04.jpeg,9d0fec87-7012-4bda-b87d-0140e17adc83.jpeg,f01d2fb3-b34a-4147-b87b-3dd38f5dd0d2.jpeg,88fd6664-2017-41db-8d16-2848b678ba3d.jpeg,eed001df-beda-414e-8542-5a92e7e59ac4.jpeg,8054dafa-56f1-4fc7-b2f0-d4cfdc0dc40e.jpeg,daac05b0-9289-456d-9886-c7bb8dfa92ec.jpeg,cb9c1a24-80a9-4af6-bccb-89fa572d4b11.jpeg,5430e578-ba7c-4ff6-b1b7-ff9982c9b0d4.jpeg,0cc8086a-3a28-4173-afbb-66df8abf22fa.jpeg,a01ed2b8-41b5-4212-9827-48e4faf54d46.jpeg,200686c5-32e0-4651-8961-2e09ef2fd90e.jpeg,cc80e7cf-7301-423d-beb2-8e5dfc3bceda.jpeg,ad26a020-bd5e-4b65-a3c5-8189fe962d41.jpeg,475984dd-5838-4264-8217-019840ea7fd7.jpeg,0b7d230d-3b8c-4ff8-9266-5327b979e115.jpeg,1f919144-9de2-4f5a-91ce-e4a5da29faf6.jpeg,81ea10c8-5eb0-41bb-a4d9-18e895916fc4.jpeg,567e4d2b-8ddf-4d98-b18a-7c937852e4fa.jpeg,0564ebc2-f0f2-4486-8527-d353c7f4eb2f.jpeg,ae5e25e8-2ba0-4848-a7ab-74b4b88ae709.jpeg,7ce0948f-cf5c-4589-b786-52cc127f2e39.jpeg,b1d84079-9fa3-486b-a73d-26c17fd3d1b2.jpeg,638f96ac-adf7-4ebd-80ca-22ca96985815.jpeg,4480875a-f9d3-47f8-9227-15fa283fd159.jpeg,e76df079-cfe1-43b1-a053-3c3537730701.jpeg,18c024e2-ad55-423e-b02f-1f93b7b2b178.jpeg,30526be3-6f45-4f48-92b9-06de31102e58.jpeg,0ae07c75-90f8-4999-835b-1e1530a19a7e.jpeg,1666d7d1-440e-4ebf-96bd-7fa67d6fdfe5.jpeg,e4098c8e-df85-42a1-ab59-bfbab8035a8c.jpeg"
filenames = str_files_to_process.split(",")
continue_processing = True
render_inst = MovieRenderer()
#download_file("904c43eb-b160-4e21-90d6-f49f76b42703.mp4", "sample-video.mp4")
for f in filenames:
    break
    if '.mp4' not in f:
        continue

    #if f == "151b48f1-5b44-469f-b52d-2254b49ab1c8.mp4":
    #    print('found last record')
    #    continue_processing = True
    #    continue

    if not continue_processing:
        print('.')
        continue
    print('processing: ' + f)
    tmp_file = "tmp" + f
    download_success = download_file(f, tmp_file)
    if not download_success:
        print('error downloading file: ' + f)
        break
    
    tmp_store_file = "tmpstore" + f
    render_inst.process_video_new_style(tmp_file, tmp_store_file)
    upload_file(tmp_store_file, f)
    os.remove(tmp_file)
    os.remove(tmp_store_file)


for f in filenames:
    if '.mp4' in f:
        continue

    #if f == "151b48f1-5b44-469f-b52d-2254b49ab1c8.mp4":
    #    print('found last record')
    #    continue_processing = True
    #    continue

    if not continue_processing:
        print('.')
        continue
    print('processing: ' + f)
    tmp_file = "tmp" + f
    download_success = download_file(f, tmp_file)
    if not download_success:
        print('error downloading file: ' + f)
        break
    
    tmp_store_file = "tmpstore" + f
    filepath = "./"
    watermark_image(filepath, tmp_file, tmp_store_file, "Kherem.com", filepath)
    upload_file(tmp_store_file, f)
    os.remove(tmp_file)
    os.remove(tmp_store_file)

