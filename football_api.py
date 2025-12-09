import requests

# 示例：football-data.org 拿当天所有比赛
headers = {"X-Auth-Token": "fb7f9ce7094a4539b14c5a8c4d4d04d7"}
r = requests.get("https://api.football-data.org/v4/matches", headers=headers)
print(r.json())