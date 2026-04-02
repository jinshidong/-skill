# Camera-Ready WeChat Drafts

Use this reference when the user asks for “整理成公众号稿件”“转终稿”“camera ready”“不要审稿人口吻”。

## Goal

Convert a reviewer-style Markdown draft into two files:

- `<stem>.camera-ready.md`: front matter + publishable正文
- `<stem>.camera-ready.notes.md`: 备选标题、封面 prompt、正文配图 prompt、推荐摘要

## Required Style Shift

Do not keep reviewer-facing phrasing such as:

- “给审稿人看”
- “供参考”
- “说明一下”
- “下面几个值得看”
- “如果你最近只想快速抓住……”

The main draft must read like a finished公众号成稿:

- strong opening within the first 2-3 paragraphs
- clear narrative spine instead of list-like commentary
- decisive conclusion
- natural reader-facing tone

## Internal Checklist

Before rewriting, settle these points internally:

- core thesis
- 2-3 supporting angles
- persuasion strategy
- emotional rhythm
- 2-3 memorable lines
- reader interaction hook

This is inspired by Viral Writer’s “think first, then write” workflow, but the final output must stay clean and publishable.

## Output Rules

- Main draft keeps only front matter +正文
- Notes file keeps:
  - 5 alternative titles
  - 1 cover prompt
  - 2-4 body image prompts
  - recommended digest
- Do not publish the notes file

## Metadata Rules

- Normalize the camera-ready front matter with resolved values
- If the real author is unknown, set author to `路人甲`
- Fill an explicit `cover` path into the camera-ready front matter
- Preserve useful fields such as `date`, `permalink`, and `tags`

## Publish Handoff

After the rewrite:

1. run `scripts/inspect.sh article.md`
2. run `scripts/dry_run.sh article.md`
3. if validation passes, publish via `scripts/create_draft.sh article.md`

These commands automatically prefer `article.camera-ready.md` when it exists.
