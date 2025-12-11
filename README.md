# MatchRecommender
一个轻量级的命令行工具，结合足球和电竞的赛程，再通过 OpenAI 打分提示生成个性化的比赛推荐列表。

## 前置条件
- 需要 Python 3.8 或更高版本。
- 依赖包手动安装：
  ```sh
  pip install openai python-dotenv requests
  ```
- 在项目根目录创建 `.env`，填入 `OPENAI_API_KEY=sk-...`，以便调用 OpenAI Responses API。

## 配置
1. 编辑 `user_profile.txt`，写入你偏好的联赛、球队、关注点等内容；文件必须存在且非空，否则推荐模块无法生成上下文。
2. 按需在 `.env` 中添加 `FOOTBALL_API_TOKEN`（必需）和可选的 `FOOTBALL_COMPETITIONS`（例如 `2001,2014`），每次运行时会直接请求 `football-data.org` 获取赛程数据。

## 使用方式
```sh
python match_recommender.py
```
脚本流程：加载用户画像 → 请求足球 API → 转换成标准赛程结构 → 拼接成 prompt → 传给 `gpt-5-nano` 得到排序后的推荐。结果会输出推荐分、比赛信息与模型的理由。

## 获取赛程
- 通过 `/matches` 接口拉取默认状态（`SCHEDULED`）的比赛，并会额外根据 `.env` 里配置的 `FOOTBALL_COMPETITIONS` 进行筛选。
- 为了控制获取范围，代码里还将固定窗口（例如未来 3 天）加到请求参数里，确保只拿到最近的赛程。
- 如果没有设置 token、网络失败或 API 返回错误，程序会打印提示并终止，此时修复问题后重新运行。

## 其他提示
- `football.py` 负责从 API 获取并标准化赛程数据，`match_recommender.py` 才是推荐入口。
- 保持 `.env` 和 `user_profile.txt` 内容与当前兴趣一致，有助于输出更相关的推荐结果。
