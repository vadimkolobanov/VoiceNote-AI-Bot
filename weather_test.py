import requests

city = "Montreal"  # замените на город из базы
url = "https://nominatim.openstreetmap.org/search"
params = {
    "q": city,
    "format": "json",
    "accept-language": "ru",
    "limit": 5,
    "countrycodes": "ru,by,ua,kz,kg,uz,md,am,ge,az,ca"
}
headers = {"User-Agent": "YourApp/1.0"}

response = requests.get(url, params=params, headers=headers)
print(response.json())
