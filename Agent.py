import os
import requests
from flask import Flask, render_template, request, jsonify

AZURE_API_KEY="2zAOSQrTAAYjjDOEn5Np3gPNoW6jNQWGX9h2kj2SCRiylYVdJ2wGJQQJ99BEACGhslBXJ3w3AAAFACOGyoqY"
AZURE_ENDPOINT="https://appian-ai-vision.cognitiveservices.azure.com/"
GOOGLE_API_KEY="AIzaSyCOUVzhnslVLptqvqG3UKzi2RV7C8K7uUo"
GOOGLE_CSE_ID="43d4522b81a22400e"

AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")

def clean_description(desc):
    prepositions = [
        " in ", " on ", " at ", " by ", " for ", " about ", " against ", " among ",
        " around ", " before ", " behind ", " below ", " beside ", " between ", " during ",
        " inside ", " near ", " outside ", " over ", " through ", " under ", " until ",
        " up ", " via "
    ]
    desc_lower = desc.lower()
    indexes = [desc_lower.find(prep) for prep in prepositions if desc_lower.find(prep) != -1]

    if indexes:
        first_prep_index = min(indexes)
        return desc[:first_prep_index].strip()
    else:
        return desc.strip()

def replace_color(description, new_color):
    colors = ["white", "black", "red", "blue", "green", "yellow", "grey", "gray", "orange", "purple", "pink", "brown", "beige"]
    desc_lower = description.lower()
    for color in colors:
        if color in desc_lower:
            # Replace color word with new_color (case-insensitive)
            # We do a simple replace to handle "white shirt" -> "green shirt"
            desc_lower = desc_lower.replace(color, new_color)
            return desc_lower
    # If no color found, just add new color at the start
    return f"{new_color} {description}"

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    description = None
    product_links = []

    if request.method == "POST":
        image = request.files.get("image")
        if image:
            headers = {
                "Ocp-Apim-Subscription-Key": AZURE_API_KEY,
                "Content-Type": "application/octet-stream"
            }
            params = {"visualFeatures": "Description,Tags,Objects,Brands"}
            response = requests.post(
                f"{AZURE_ENDPOINT}/vision/v3.2/analyze",
                headers=headers,
                params=params,
                data=image.read()
            )
            result = response.json()
            try:
                raw_description = result["description"]["captions"][0]["text"]
                description = clean_description(raw_description)
                # Append brand names if any
                brands = result.get("brands", [])
                if brands:
                    brand_names = ", ".join([brand["name"] for brand in brands])
                    description += f" by {brand_names}"
                product_links = search_google_images(description)
            except (KeyError, IndexError):
                description = "No description found."

    return render_template("index.html", description=description, results=product_links)

@app.route("/chat", methods=["POST"])
def chat():
    """
    Expected JSON:
    {
      "message": "show me this in green",
      "imageData": <base64 string of selected image>
    }
    """
    data = request.get_json()
    user_message = data.get("message", "").lower()
    image_data = data.get("imageData")

    if not image_data:
        return jsonify({"error": "No image data provided"}), 400

    import base64

    try:
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
    except Exception:
        return jsonify({"error": "Invalid image data"}), 400

    # Call Azure Vision API on the selected image bytes to get fresh description + brands
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_API_KEY,
        "Content-Type": "application/octet-stream"
    }
    params = {"visualFeatures": "Description,Tags,Objects,Brands"}
    response = requests.post(
        f"{AZURE_ENDPOINT}/vision/v3.2/analyze",
        headers=headers,
        params=params,
        data=image_bytes
    )
    result = response.json()

    try:
        raw_description = result["description"]["captions"][0]["text"]
        description = clean_description(raw_description)

        # Append brand names if any (fresh extraction on the selected image)
        brands = result.get("brands", [])
        if brands:
            brand_names = ", ".join([brand["name"] for brand in brands])
            description += f" by {brand_names}"

    except (KeyError, IndexError):
        description = "No description found."

    # Detect requested color from user message and replace color in description
    requested_color = None
    colors = ["white", "black", "red", "blue", "green", "yellow", "grey", "gray", "orange", "purple", "pink", "brown", "beige"]
    for color in colors:
        if color in user_message:
            requested_color = color
            break

    if requested_color:
        description = replace_color(description, requested_color)

    # Search Google Images with updated description
    product_links = search_google_images(description)

    reply = f"Showing results for: '{description}'"
    return jsonify({
        "reply": reply,
        "results": product_links
    })


def search_google_images(query):
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "cx": cse_id,
        "key": api_key,
        "searchType": "image",
        "num": 5
    }

    response = requests.get(search_url, params=params)
    results = response.json()

    items = []
    for item in results.get("items", []):
        items.append({
            "title": item.get("title"),
            "link": item.get("link"),  # direct image URL
            "contextLink": item.get("image", {}).get("contextLink")  # page containing image
        })
    return items


if __name__ == "__main__":
    app.run(debug=True)


