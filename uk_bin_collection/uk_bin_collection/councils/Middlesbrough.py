from uk_bin_collection.uk_bin_collection.common import (
    check_paon,
    check_postcode,
    datetime,
    requests,
    timedelta,
)
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs: str) -> dict[str, list[dict[str, str | datetime]]]:
        if (postcode := kwargs.get("postcode")) is None:
            raise KeyError("Missing: postcode")
        if (house_number := kwargs.get("house_number")) is None:
            raise KeyError("Missing: house_number")
        check_postcode(postcode)
        check_paon(house_number)
        data: dict[str, list[dict[str, str | datetime]]] = {"bins": []}

        s = requests.session()

        place_lookup_url = "https://api.eu.recollect.net/api/areas/MiddlesbroughUK/services/"\
            f"50005/address-suggest?q={postcode}&locale=en-GB"
        place_lookup_response = s.get(place_lookup_url)
        place_lookup_response.raise_for_status()

        postcode_place_id = ""
        for p in place_lookup_response.json():
            if p.get("name").upper() == postcode.upper():
                postcode_place_id = p.get("qualifier_id")

        # get from the place lookup url
        place_id = ""
        place_list_url = "https://api.eu.recollect.net/api/areas/MiddlesbroughUK/services/"\
            "50005/pages/en-GB/place_calendar.json?widget_config=%7B%22area%22%3A%22"\
            "MiddlesbroughUK%22%2C%22name%22%3A%22calendar%22%2C%22base%22%3A%22"\
            "https%3A%2F%2Frecollect.net%22%2C%22third_party_cookie_enabled"\
            "%22%3A1%2C%22place_not_found_in_guest%22%3A0%2C%22is_guest_service%22%3A0%7D"
        s.headers["X-Recollect-Place"] = f"qualifier.{postcode_place_id}:50005"
        full_place_list_response = s.get(place_list_url)

        response_section = full_place_list_response.json().get("sections")
        if response_section[0].get("class", "") == "QualifiedPlaces":
            places_list = response_section[0].get("rows")
        else:
            places_list = response_section[1].get("rows")
        for p in places_list:
            if house_number.upper().startswith("FLAT"):
                if house_number.upper() in p.get("label").upper():
                    place_id = p.get("place_id").split(":")[0]
            else:
                if house_number == p.get("label").split()[0]:
                    place_id = p.get("place_id").split(":")[0]

        start_date = (datetime.now() - timedelta(weeks=1)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(weeks=52)).strftime("%Y-%m-%d")
        place_details_url = f"https://api.eu.recollect.net/api/places/{place_id}/services/"\
            f"50005/events?nomerge=1&hide=reminder_only&after={start_date}&"\
            f"before={end_date}&locale=en-GB"
        place_details_response = s.get(place_details_url)
        place_details_response.raise_for_status()

        bin_events = place_details_response.json().get("events", {})
        for b in bin_events:
            flags: list[dict[str, str]] = b.get(
                "flags") if isinstance(b.get("flags"), list) else list()
            raw_type: str = flags[0].get("subject", "").upper()
            bin_type = ""
            if raw_type == "REFUSE":
                bin_type = "Refuse Bin"
            elif raw_type == "GARDEN":
                bin_type = "Garden Waste Bin"
            elif raw_type == "RECYCLING":
                bin_type = "Recycling Bin"
            if bin_type != "":
                dict_data: dict[str, str | datetime] = {
                    "type": bin_type,
                    "collectionDate": datetime.strptime(b.get("day", ""), "%Y-%m-%d")
                }
                data["bins"].append(dict_data)

        return data
