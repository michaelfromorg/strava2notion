"""
Make sure to allow the integration access to the page with the database.

See: https://developers.notion.com/reference/query-a-database
"""

from notion_client import Client

from strava2notion.config import DATABASE_ID, TOKEN_V3

notion = Client(auth=TOKEN_V3)


def upload_to_notion(parent, data):
    """
    Upload Strava data to Notion.
    """
    print("Uploading", data.name, "to Notion")

    date = str(data.start_date_local)

    distance = round(data.distance / 1000, 2)

    time = data.moving_time
    timeh = round(time / 3600, 2)

    if data.weighted_average_watts is None:
        power = 0
    else:
        power = data.weighted_average_watts

    link = "https://strava.com/activities/" + str(data.id)

    properties = {
        "Name": {
            "type": "title",
            "title": [{"type": "text", "text": {"content": data.name}}],
        },
        "Type": {"type": "select", "select": {"name": data.type}},
        "Length": {"type": "number", "number": distance},
        "Time": {"type": "number", "number": timeh},
        "Power": {"type": "number", "number": power},
        "Elevation": {"type": "number", "number": data.total_elevation_gain},
        "Date": {"type": "date", "date": {"start": date}},
        "Strava Link": {"type": "url", "url": link},
    }

    notion.pages.create(parent=parent, properties=properties)


def most_recent_activity_date(id=DATABASE_ID):
    """
    Get the most recent activity data from Notion.
    """
    data = notion.databases.query(database_id=id, page_size=1)

    results = data["results"]
    result_data = dict(results[0])

    properties = result_data["properties"]

    Date = properties["Date"]
    date = Date["date"]
    start_date = date["start"]
    start_date = start_date[0:10]

    # TODO(michaelfromyeg): WTF?
    # add a day to not duplicate, may miss double days though
    # end_char = int(start_date[-1]) + 1
    start_date = start_date[0:9]  # + str(end_char)

    print("Last date found:", start_date)
    return start_date
