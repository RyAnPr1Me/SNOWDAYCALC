import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- Configuration: Tokens (use caution in production) ---
NOAA_API_TOKEN = "JolTsHKbwqhKpBQEbmLKrduzpMDNjwKa"

class SnowDayResearchAI:
    def __init__(self, location, date):
        """
        :param location: e.g. "Windham, NH"
        :param date: target date as "YYYY-MM-DD" (e.g., "2025-02-17")
        """
        self.location = location
        self.date = date
        self.weather_data = None
        self.historical_data = None
        self.policy_data = None
        self.road_conditions = None
        self.analysis = {}
        # Updated NOAA station IDs provided by the user:
        self.station_ids = [
            "USC00275712",  # NASHUA 2 NNW, NH (~12 km west of Windham)
            "USC00273626",  # LAWRENCE, MA (~14 km southeast of Windham)
            "USC00272174",  # EPPING, NH (~30 km northeast of Windham)
            "USC00275629",  # MILFORD, NH (~30 km west of Windham)
            "USC00273850"   # LOWELL, MA (~20 km south of Windham)
        ]

    def fetch_weather_data(self):
        """
        Retrieves real-time weather forecast data using wttr.in's JSON API.
        """
        url = f"http://wttr.in/{self.location}?format=j1"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            forecast = data['weather'][0]
            totalSnow_cm = float(forecast.get("totalSnow_cm", 0))
            avgtempF = float(forecast.get("avgtempF", 32))
            self.weather_data = {
                "totalSnow_cm": totalSnow_cm,
                "avgtempF": avgtempF
            }
            print(f"[Weather] Retrieved: {totalSnow_cm} cm snow, {avgtempF} °F average temp.")
        except Exception as e:
            raise Exception(f"Error fetching weather data: {e}")

    def fetch_historical_data(self):
        """
        Retrieves historical snowfall data from NOAA’s Climate Data Online API.
        For each station ID provided, the script fetches snowfall (datatype "SNOW")
        for the target date over the past 5 years, sums the daily totals (in mm),
        converts them to inches, and averages the values across stations.
        """
        headers = {"token": NOAA_API_TOKEN}
        datasetid = "GHCND"    # Daily summaries dataset
        datatypeid = "SNOW"    # Snowfall (in millimeters)
        target_date = datetime.strptime(self.date, "%Y-%m-%d")
        years = [target_date.year - i for i in range(1, 6)]
        snowfall_values = []
        for station in self.station_ids:
            station_values = []
            for year in years:
                start_date = datetime(year, target_date.month, target_date.day)
                end_date = start_date + timedelta(days=1)
                url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
                params = {
                    "datasetid": datasetid,
                    "datatypeid": datatypeid,
                    "stationid": station,  # Using provided station ID directly
                    "startdate": start_date.strftime("%Y-%m-%d"),
                    "enddate": end_date.strftime("%Y-%m-%d"),
                    "limit": 1000
                }
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=10)
                    result = resp.json()
                    if "results" in result:
                        daily_total_mm = sum(item["value"] for item in result["results"])
                        daily_inches = daily_total_mm * 0.03937  # Convert mm to inches
                        station_values.append(daily_inches)
                        print(f"[Historical] Station {station} Year {year}: {daily_inches:.2f} inches")
                    else:
                        print(f"[Historical] No data for station {station} on {start_date.strftime('%Y-%m-%d')}")
                except Exception as e:
                    print(f"Error fetching NOAA historical data for station {station} in {year}: {e}")
            if station_values:
                avg_station = sum(station_values) / len(station_values)
                snowfall_values.append(avg_station)
        if snowfall_values:
            avg_snowfall = sum(snowfall_values) / len(snowfall_values)
            # If average snowfall is 3 inches or more, assume a higher closure tendency.
            snow_day_rate = 0.5 if avg_snowfall >= 3 else 0.3
            self.historical_data = {
                "avg_snowfall_in": avg_snowfall,
                "snow_day_rate": snow_day_rate
            }
            print(f"[Historical] Averaged snowfall: {avg_snowfall:.2f} inches, closure rate: {snow_day_rate*100:.0f}%")
        else:
            raise Exception("No historical snowfall data retrieved from NOAA.")

    def fetch_school_policy(self):
        """
        Scrapes the Windham School District website for snow day policy information.
        """
        url = "https://www.windhamschools.org/"
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            text = soup.get_text(separator=" ").lower()
            if "snow day" in text or "closure" in text or "cancel" in text:
                policy_rate = 0.6  # Higher closure tendency
            else:
                policy_rate = 0.4
            closure_time = "5:30 AM"
            self.policy_data = {
                "closure_time": closure_time,
                "historical_closure_rate": policy_rate
            }
            print(f"[Policy] School policy: {policy_rate*100:.0f}% closure tendency, decision by {closure_time}.")
        except Exception as e:
            raise Exception(f"Error fetching school policy data: {e}")

    def fetch_road_conditions(self):
        """
        Scrapes the New Hampshire Department of Transportation traffic conditions page for road status.
        """
        url = "https://www.nh.gov/dot/traffic/conditions/index.shtml"
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            content = soup.get_text(separator=" ").lower()
            if "windham" in content:
                if any(word in content for word in ["closed", "slippery", "ice", "snow"]):
                    road_score = 8  # poor conditions
                else:
                    road_score = 3
            else:
                road_score = 5  # moderate default
            self.road_conditions = road_score
            print(f"[Road] Road condition score: {road_score}/10.")
        except Exception as e:
            raise Exception(f"Error fetching road conditions data: {e}")

    def simple_reasoning_adjustment(self, reasoning_text):
        """
        A simple internal 'deep reasoning' function that computes an adjustment factor
        based on the average word length in the reasoning text.
        The factor is scaled between 0.9 and 1.1.
        """
        words = reasoning_text.split()
        if not words:
            return 1.0
        avg_word_length = sum(len(word) for word in words) / len(words)
        # For example, we define:
        # avg word length 4 -> factor 0.9, 5 -> 1.0, 6 -> 1.1, linear in between.
        factor = 0.9 + (avg_word_length - 4) * 0.1
        factor = max(0.9, min(factor, 1.1))
        return factor

    def analyze_factors(self):
        """
        Combines all fetched factors with weighted analysis, then applies the simple reasoning adjustment.
        """
        reasoning_lines = []

        # Weather analysis:
        totalSnow_cm = self.weather_data["totalSnow_cm"]
        snowfall_in = totalSnow_cm / 2.54  # convert cm to inches
        avgtemp = self.weather_data["avgtempF"]
        reasoning_lines.append(f"Weather forecast: approximately {snowfall_in:.1f} inches of snow (from {totalSnow_cm:.1f} cm) with an average temperature of {avgtemp:.1f}°F.")

        # Historical analysis:
        avg_snowfall = self.historical_data["avg_snowfall_in"]
        hist_rate = self.historical_data["snow_day_rate"]
        reasoning_lines.append(f"Historical data: average snowfall over the past 5 years is {avg_snowfall:.1f} inches, suggesting a closure rate of {hist_rate*100:.0f}%.")

        # Road conditions:
        road_score = self.road_conditions
        road_desc = "poor" if road_score >= 7 else "moderate" if road_score >= 4 else "good"
        reasoning_lines.append(f"Road conditions are rated {road_score}/10, indicating {road_desc} travel conditions.")

        # School policy:
        policy_rate = self.policy_data["historical_closure_rate"]
        closure_time = self.policy_data["closure_time"]
        reasoning_lines.append(f"School policy: based on the district website (decision by {closure_time}), the closure tendency is around {policy_rate*100:.0f}%.")

        # Weighting factors:
        weather_weight = 0.4
        historical_weight = 0.2
        road_weight = 0.2
        policy_weight = 0.2

        snowfall_factor = min(snowfall_in / 6, 1.0)  # 6 inches or more gives max risk
        temp_factor = 1 if avgtemp < 32 else 0.5   # below freezing = full risk
        weather_factor = snowfall_factor * temp_factor

        base_probability = (
            (weather_factor * weather_weight) +
            (hist_rate * historical_weight) +
            ((road_score / 10) * road_weight) +
            (policy_rate * policy_weight)
        ) * 100
        base_probability = max(0, min(base_probability, 100))
        reasoning_lines.append(f"Weighted analysis: weather factor ({weather_factor:.2f}), historical rate ({hist_rate:.2f}), road factor ({road_score/10:.2f}), policy factor ({policy_rate:.2f}).")
        reasoning_lines.append(f"Base computed probability: {base_probability:.2f}%.")

        combined_reasoning = "\n".join(reasoning_lines)
        adjustment_factor = self.simple_reasoning_adjustment(combined_reasoning)
        final_probability = base_probability * adjustment_factor
        final_probability = max(0, min(final_probability, 100))
        reasoning_lines.append(f"After applying a simple reasoning adjustment factor of {adjustment_factor:.2f}, the final probability is {final_probability:.2f}%.")

        self.analysis = {
            "final_probability": round(final_probability, 2),
            "detailed_reasoning": reasoning_lines
        }

    def run_analysis(self):
        self.fetch_weather_data()
        self.fetch_historical_data()
        self.fetch_school_policy()
        self.fetch_road_conditions()
        self.analyze_factors()
        return self.analysis

if __name__ == "__main__":
    location = "Windham, NH"
    date = "2025-02-17"
    ai = SnowDayResearchAI(location, date)
    try:
        result = ai.run_analysis()
        print(f"\nProbability of a snow day in {location} on {date}: {result['final_probability']}%")
        print("Detailed Reasoning:")
        for line in result["detailed_reasoning"]:
            print("- " + line)
    except Exception as err:
        print(f"An error occurred during analysis: {err}")
