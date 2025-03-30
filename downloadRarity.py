import sqlite3
import requests

def download_images(db_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch the large image URL and rarity for each card
    cursor.execute("""SELECT rarity, images FROM cards WHERE card_id IN (
    SELECT MIN(card_id)
    FROM cards
    GROUP BY rarity
)
ORDER BY rarity ASC;""")
    images = cursor.fetchall()
    
    # Close the cursor and connection
    cursor.close()
    conn.close()
    
    # Create a directory for images if it doesn't exist
    import os
    if not os.path.exists('images'):
        os.makedirs('images')
    
    # Download and save each image
    for rarity, image_info in images:
        if image_info:
            # Extract the URL for the large image
            import json
            image_urls = json.loads(image_info)
            large_image_url = image_urls['large']
            
            # Define the file path, incorporating rarity and ensuring no overwrites by using an increment
            file_path = f'images/{rarity}.png'
            counter = 1
            while os.path.exists(file_path):
                file_path = f'images/{rarity}_{counter}.png'
                counter += 1
            
            # Download and save the image
            response = requests.get(large_image_url)
            if response.status_code == 200:
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                print(f'Downloaded image saved as {file_path}')
            else:
                print(f'Failed to download image from {large_image_url}')

# Specify the path to your database
database_path = 'pokemon_cards.db'
download_images(database_path)
