from app.agents.dietitian import DietitianAgent
from app.agents.document import DocumentAgent
from app.agents.fashion import FashionDesignerAgent
from app.agents.finance import FinanceAgent
from app.agents.health import HealthAgent
from app.agents.hotel import HotelAgent
from app.agents.insurance import InsuranceAgent
from app.agents.tour_guide import TourGuideAgent
from app.agents.transportation import TransportationAgent
from app.agents.travel_planner import TravelPlannerAgent
from app.agents.validator import ValidatorAgent
from app.agents.weather import WeatherAgent

AGENT_CLASSES = {
    "validator": ValidatorAgent,
    "travel_planner": TravelPlannerAgent,
    "weather": WeatherAgent,
    "transportation": TransportationAgent,
    "hotel": HotelAgent,
    "tour_guide": TourGuideAgent,
    "health": HealthAgent,
    "dietitian": DietitianAgent,
    "document": DocumentAgent,
    "insurance": InsuranceAgent,
    "fashion_designer": FashionDesignerAgent,
    "finance": FinanceAgent,
}


def build_agent(agent_id: str):
    return AGENT_CLASSES[agent_id]()
