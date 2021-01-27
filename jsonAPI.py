from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from landing import app

web_search_config = app.config["REPORT_CONFIG"]["WEB_SEARCH"]
api_key = web_search_config["api_key"]
cse_id = web_search_config["cse_id"]


def google_search(search_term, **kwargs):
    try:
        service = build("customsearch", "v1", developerKey=api_key, cache_discovery=False)
        response = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    except HttpError as err:
        print(err)
        return []
    if 'items' in response.keys():
        resulted_link_snippet_pairs = [(item['link'], item['snippet']) for item in response['items']]
        return resulted_link_snippet_pairs
    return []
