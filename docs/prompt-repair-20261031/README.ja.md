# MOSSプロンプト全件点検・修正記録

2026-10-31。対象はローカル配布コピーとHugging Face全件オンラインデモ。原本は変更していません。後続の配布更新でv0.1.2 ZIPとGitHub Releaseにも反映します。

## 結果

- 全34,249件を規則で点検：キャラクター33,935件・スタイル314件。
- コピー用本文の変更：5,641件。残りは今回の修正規則の対象外として維持。内容が正しいと全件認定したものではない。
- 修正済み再生成用本文：33,785件。共通構図の耳・尻尾・足の列挙は33,775件で中立表現へ置換。
- コピー用ファイルの参照キーの破損を3件修復。
- スタイル314件の元のコピー文・生成文は維持。
- 画像・保存ワークフロー・元タグの全102,747ファイルのSHA256不変を照合。
- 元本体の保護ファイルと現行Release ZIPのSHA256不変。

## 修正規則

1. 再生成用だけで、`Keep the entire head, all ears if present, tail tip if present, and all feet completely visible inside the frame.` を `Keep the entire character visible within the frame, with space around the silhouette.` へ置換。人間・クリーチャーとも中立な全身構図にする。
2. 外見タグのponytail/twintails等の結び髪を、髪だと明示する英文に整理。名前・作品名・動物のtail、fox tail等は置換しない。髪の意味の維持を意図した文章整理であり、誤生成の原因が髪型語だと実証したものではない。
3. 外見にandroid/robotが明記される場合のみ、矛盾するhumanという種別指定を取り除く。性別を残し、一般の人間・cyborg・動物耳などを推測で種別変更しない。
4. 外見の完全一致の重複語を整理。元のタグ列は出典として保持。
5. `generation_prompt`とworkflow.jsonは実生成の記録として保持。修正文は`reuse_generation_prompt`へ分離。拡大画面に日英の説明とコピー操作を追加した。

## 未解決・未実施

15,946件に元データの確認フラグがある。内訳は重複計上：source_multiple_hair_colors=4623, source_multiple_tied_hairstyles=283, source_multiple_eyes_colors=4119, source_human_creature_conflict=132, appearance_not_supplied=7894, source_multiple_gender_tags=132。

外見未指定は情報不足であり誤りの確定ではない。複数の髪色・目色・髪型も形態違いを含む可能性がある。正解の特徴を全キャラクターについて公式資料で照合したわけではなく、根拠なく一方を削除したり不足する衣装を捏造していない。

GPU生成・再生成・画像の合否判定・尻尾の発生率測定は未実施。同条件で比較しない限り、修正によって尻尾が減った／キャラクターが正しくなったとは言えない。コピー用本文には元々共通のtail構図文は入っておらず、コピーだけで起きる問題と生成用共通文を区別する。

## 利用方法

- カードの「プロンプトコピー」：現在の再利用用キャプション。
- 拡大画面の「再生成用をコピー」：構図等も含む修正版の全文。ComfyUIのPositiveを全文置換して使う。
- 「当時の生成ワークフローを開く」：表示画像を生成した当時のJSON。修正前のプロンプトを含む。
- 元画像の埋め込みメタデータと元タグも履歴。新しい生成用文への自動置換はしていない。
- Release ZIPのこのフォルダーに `revised-prompts.csv`（全件修正文）と `review-needed.csv`（元データ要確認一覧）を同梱。。

## 検証

ルールテスト、全件の登録値とsidecar一致、全件の実ローカルAPI返却値、原本・ZIP・全画像/workflow/元タグのSHA一致を確認。Chromeで実配布サーバーと公開デモの検索・画像拡大・通常プロンプトと再生成用プロンプトのコピーを確認。Hugging Faceは固定親コミットを確認してメタデータだけ更新し、変更10ファイルのリモートハッシュ、全画像マニフェスト不変を確認。

この修正は更新版v0.1.2 ZIP・配布コピー・Hugging Face全件デモに収録します。GitHubには更新規則と日英文書を公開。120枚のGitHub Pagesサンプルは別の従来プレビューです。旧ZIPはbefore-prompt-revision名で保持します。
