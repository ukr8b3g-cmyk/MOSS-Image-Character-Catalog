# Back to top / 一番上に戻る — 2026-10-31

The local catalog and online demos now have a floating arrow at the lower right. It appears after scrolling 400 px down and hides near the top. Click it, or focus it and press Enter, to return to the page heading. It works in both Characters and Styles, follows the selected English/Japanese language and respects reduced-motion preferences. The button stays clear of mobile safe areas.

ローカルカタログとオンラインデモの右下に「一番上に戻る」矢印を追加しました。400px以上スクロールすると表示され、クリック／フォーカスしてEnterで先頭へ戻ります。キャラクター・スタイル両方、日英表示、動きを減らす設定、モバイルの安全領域に対応します。

The v0.1.2 ZIP was selectively updated with 7-Zip. Images, prompt revisions, original generation workflows, catalog records and review decisions are unchanged. The preceding ZIP and checksum are retained as before-back-to-top. Use the current SHA256SUMS.txt from the Release page.

配布ZIPは7-Zipで必要なファイルだけ更新しました。画像・修正版プロンプト・当時のワークフロー・登録データ・判定は維持。直前のZIPとチェックサムはbefore-back-to-top名で保持します。照合にはReleaseの最新SHA256SUMS.txtを使用してください。

Chrome checks covered scrolling, return to scrollY=0, hiding at the top, both catalog tabs, bilingual labels and Enter activation in the local application and the public Hugging Face app. The surrounding Hugging Face page's embedded frame remained loading in that session; the published app itself was tested directly. JavaScript syntax and unchanged compressed archive payloads are checked again during packaging.
