import os
import logging
from googleapiclient.discovery import build
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import jsonify
from google.cloud import storage

logging.basicConfig(level=logging.INFO)

def download_file_from_gcs(bucket_name, source_blob_name, destination_file_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
        logging.info(f"Downloaded {source_blob_name} to {destination_file_name}")
    except Exception as e:
        logging.error(f"Error downloading file from GCS: {e}")
        raise

def upload_file_to_gcs(bucket_name, destination_blob_name, source_file_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        logging.info(f"Uploaded {source_file_name} to {destination_blob_name}.")
    except Exception as e:
        logging.error(f"Error uploading file to GCS: {e}")
        raise

def read_google_sheet():
    try:
        service = build('sheets', 'v4')
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId='1qo79conkHLMbBh6B4zxg1z0ingmVFFABGSPkbSNvYEQ',
                                    range='Sheet1').execute()
        values = result.get('values', [])
        logging.info("Google Sheet data retrieved successfully")
        return values
    except Exception as e:
        logging.error(f"Error reading Google Sheet: {e}")
        raise

def generate_certificate(name, position):
    template_path = "/tmp/certificate_job_template.png"  # The updated template path
    font_path = "/tmp/Montserrat-SemiBold.ttf"  # The font path

    try:
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)

        # Drawing the Name
        name_font_size = 80
        name_font = ImageFont.truetype(font_path, name_font_size)
        name_text = name.upper()
        name_width, name_height = draw.textsize(name_text, font=name_font)
        name_x = (img.width - name_width) / 2
        name_y = 650  # Adjust Y position for name
        draw.text((name_x, name_y), name_text, font=name_font, fill="black")

        # Drawing the Position
        position_font_size = 40
        position_font = ImageFont.truetype(font_path, position_font_size)
        position_text = f"has been employed as {position}"
        position_width, position_height = draw.textsize(position_text, font=position_font)
        position_x = (img.width - position_width) / 2
        position_y = 800  # Adjust Y position for position text
        draw.text((position_x, position_y), position_text, font=position_font, fill="black")
        
        # Saving the image and converting to PDF
        temp_image_path = f"/tmp/{name}_certificate_image.png"
        img.save(temp_image_path, format='PNG')

        pdf_output_path = f"/tmp/{name}_certificate.pdf"
        c = canvas.Canvas(pdf_output_path, pagesize=letter)
        img_width, img_height = img.size
        aspect_ratio = img_width / img_height
        new_width = letter[0]
        new_height = new_width / aspect_ratio

        if new_height > letter[1]:
            new_height = letter[1]
            new_width = new_height * aspect_ratio

        x = (letter[0] - new_width) / 2
        y = (letter[1] - new_height) / 2
        c.drawImage(temp_image_path, x, y, width=new_width, height=new_height)
        c.save()

        upload_file_to_gcs('pdf_generator_res', f"certificates/{name}_certificate.pdf", pdf_output_path)
        logging.info(f"Certificate generated and uploaded for {name}")

        os.remove(temp_image_path)
        os.remove(pdf_output_path)

        return pdf_output_path

    except Exception as e:
        logging.error(f"Error generating certificate for {name}: {e}")
        raise

def main(request):
    bucket_name = 'pdf_generator_res'
    template_blob_name = 'certificate_job_template.png'  # Update to your new template
    font_blob_name = 'Montserrat-SemiBold.ttf'

    try:
        download_file_from_gcs(bucket_name, template_blob_name, '/tmp/certificate_job_template.png')
        download_file_from_gcs(bucket_name, font_blob_name, '/tmp/Montserrat-SemiBold.ttf')

        sheet_data = read_google_sheet()

        for row in sheet_data:
            if row:
                name = row[0]
                position = row[1] if len(row) > 1 else "Position Not Provided"
                if name:
                    generate_certificate(name, position)

        return jsonify({"status": "Certificates generated successfully"}), 200

    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return jsonify({"status": "Error", "message": str(e)}), 500
