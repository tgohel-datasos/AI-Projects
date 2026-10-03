from app.tools.geo import haversine_km

AIRPORTS: list[dict] = [
    {"iata": "AMD", "name": "Sardar Vallabhbhai Patel International", "city": "Ahmedabad", "lat": 23.0772, "lon": 72.6347},
    {"iata": "BOM", "name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "lat": 19.0896, "lon": 72.8656},
    {"iata": "DEL", "name": "Indira Gandhi International", "city": "Delhi", "lat": 28.5562, "lon": 77.1000},
    {"iata": "BLR", "name": "Kempegowda International", "city": "Bengaluru", "lat": 13.1979, "lon": 77.7063},
    {"iata": "MAA", "name": "Chennai International", "city": "Chennai", "lat": 12.9941, "lon": 80.1709},
    {"iata": "HYD", "name": "Rajiv Gandhi International", "city": "Hyderabad", "lat": 17.2403, "lon": 78.4294},
    {"iata": "CCU", "name": "Netaji Subhas Chandra Bose International", "city": "Kolkata", "lat": 22.6520, "lon": 88.4463},
    {"iata": "COK", "name": "Cochin International", "city": "Kochi", "lat": 10.1520, "lon": 76.4019},
    {"iata": "CJB", "name": "Coimbatore International", "city": "Coimbatore", "lat": 11.0300, "lon": 77.0434},
    {"iata": "TRV", "name": "Thiruvananthapuram International", "city": "Thiruvananthapuram", "lat": 8.4821, "lon": 76.9200},
    {"iata": "GOI", "name": "Goa Dabolim", "city": "Goa", "lat": 15.3808, "lon": 73.8314},
    {"iata": "GOX", "name": "Manohar International (Mopa)", "city": "Goa", "lat": 15.7443, "lon": 73.8606},
    {"iata": "UDR", "name": "Maharana Pratap Airport", "city": "Udaipur", "lat": 24.6177, "lon": 73.8911},
    {"iata": "JAI", "name": "Jaipur International", "city": "Jaipur", "lat": 26.8242, "lon": 75.8122},
    {"iata": "PNQ", "name": "Pune Airport", "city": "Pune", "lat": 18.5822, "lon": 73.9197},
    {"iata": "IXC", "name": "Chandigarh Airport", "city": "Chandigarh", "lat": 30.6735, "lon": 76.7885},
    {"iata": "SXR", "name": "Sheikh ul-Alam International", "city": "Srinagar", "lat": 33.9871, "lon": 74.7743},
    {"iata": "IXB", "name": "Bagdogra Airport", "city": "Bagdogra", "lat": 26.6812, "lon": 88.3286},
    {"iata": "GAU", "name": "Lokpriya Gopinath Bordoloi International", "city": "Guwahati", "lat": 26.1061, "lon": 91.5859},
    {"iata": "PAT", "name": "Jay Prakash Narayan Airport", "city": "Patna", "lat": 25.5913, "lon": 85.0880},
    {"iata": "LKO", "name": "Chaudhary Charan Singh International", "city": "Lucknow", "lat": 26.7606, "lon": 80.8893},
    {"iata": "VNS", "name": "Lal Bahadur Shastri Airport", "city": "Varanasi", "lat": 25.4524, "lon": 82.8593},
    {"iata": "NAG", "name": "Dr. Babasaheb Ambedkar International", "city": "Nagpur", "lat": 21.0922, "lon": 79.0472},
    {"iata": "IXE", "name": "Mangaluru International", "city": "Mangaluru", "lat": 12.9613, "lon": 74.8901},
    {"iata": "MYQ", "name": "Mysore Airport", "city": "Mysuru", "lat": 12.2300, "lon": 76.6558},
    {"iata": "IXM", "name": "Madurai Airport", "city": "Madurai", "lat": 9.8345, "lon": 78.0934},
    {"iata": "ATQ", "name": "Sri Guru Ram Dass Jee International", "city": "Amritsar", "lat": 31.7096, "lon": 74.7973},
    {"iata": "BDQ", "name": "Vadodara Airport", "city": "Vadodara", "lat": 22.3362, "lon": 73.2263},
    {"iata": "STV", "name": "Surat Airport", "city": "Surat", "lat": 21.1141, "lon": 72.7418},
    {"iata": "RPR", "name": "Swami Vivekananda Airport", "city": "Raipur", "lat": 21.1804, "lon": 81.7388},
    {"iata": "BHO", "name": "Raja Bhoj Airport", "city": "Bhopal", "lat": 23.2875, "lon": 77.3374},
    {"iata": "IDR", "name": "Devi Ahilya Bai Holkar Airport", "city": "Indore", "lat": 22.7218, "lon": 75.8011},
    {"iata": "IXJ", "name": "Jammu Airport", "city": "Jammu", "lat": 32.6891, "lon": 74.8374},
    {"iata": "DED", "name": "Jolly Grant Airport", "city": "Dehradun", "lat": 30.1897, "lon": 78.1803},
    {"iata": "IXA", "name": "Maharaja Bir Bikram Airport", "city": "Agartala", "lat": 23.8860, "lon": 91.2404},
    {"iata": "IMF", "name": "Imphal Airport", "city": "Imphal", "lat": 24.7600, "lon": 93.8967},
]


def nearest_airports(lat: float, lon: float, n: int = 5) -> list[dict]:
    ranked = []
    for a in AIRPORTS:
        d = round(haversine_km(lat, lon, a["lat"], a["lon"]), 1)
        ranked.append({**a, "distance_km": d})
    ranked.sort(key=lambda x: x["distance_km"])
    return ranked[:n]
