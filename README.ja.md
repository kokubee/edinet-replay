# EDINET Replay（日本語）

> 正本は英語版 [README.md](README.md) です。食い違う場合は英語版が優先します。

**公式 EDINET ZIP → 検証可能な faithful JSON + manifest。**  
同じ原典・同じ固定 taxonomy・同じ Arelle 版 → 同じ出力ハッシュ。

![デモ: fetch → extract → validate、fact から ZIP 行へ戻る](docs/assets/demo-extract.gif)

> **現状: beta（`0.1.0b1`）。** `fetch → extract → validate` の縦経路（解決済み XBRL）は動きます。βコーパス v1（JP GAAP / IFRS / US GAAP 各1件）は [`corpus/`](corpus/) にあります。iXBRL 表示層の provenance は未完。本番保証なし・best-effort。金融庁非提携。

## 30秒デモ

コーパス例: **E04236 / S100W1NC**（JP GAAP 有報）。  
必要: Python 3.10+、`EDINET_API_KEY`、pin に一致する FSA taxonomy zip
（[`taxonomies/edinet-fsa-2024-11-01.json`](taxonomies/edinet-fsa-2024-11-01.json)）。

```console
$ pip install -e ".[xbrl]"
$ export EDINET_API_KEY=…          # ヘッダ認証のみ。CLI にキーを渡さない
$ edinet-replay fetch --document-id S100W1NC --store ./store
$ edinet-replay extract ./store/packages/S100W1NC/<raw_sha256>.zip \
    --taxonomy edinet-fsa-2024-11-01 -o ./out
$ edinet-replay validate filing  ./out/faithful-filing.json
$ edinet-replay validate manifest ./out/extraction-manifest.json
```

| 成果物 | 役割 |
|--------|------|
| `faithful-filing.json` | 解決済み fact（concept / value / context / unit / dim / nil / footnote） |
| `extraction-manifest.json` | 再現 ID（二重ハッシュ・taxonomy pin・engine・selection） |
| `source.package_path` + `source.line` | 公式 ZIP 内の行へのポインタ |

fact 例（値は**文字列**のまま）:

```json
{
  "value": "4122148000000",
  "decimals": "-6",
  "dimensions": { "concept": "jppfs_cor:Assets" },
  "source": {
    "package_path": "XBRL/PublicDoc/jpcrp030000-asr-001_E04236-000_2025-03-31_01_2025-06-23.xbrl",
    "line": 4943
  }
}
```

原典 ZIP の 4943 行目:

```xml
<jppfs_cor:Assets contextRef="Prior1YearInstant" decimals="-6"
                  unitRef="JPY">4122148000000</jppfs_cor:Assets>
```

## 目的と非目標

EDINET は公開情報でも、再現可能な利用は難しい（XBRL 構造・taxonomy 年度変化・context 欠落・正規化 DB の変換根拠の不透明さ）。

本プロジェクトは**財務解釈ではなく忠実な再現（Layer 1）**に集中します。名寄せ・正規化・比較可能性・投資助言は Layer 2（対象外）です。

- 異なる XBRL 概念を共通経済概念として統合しない  
- 経済的意味の正規化・保証をしない  
- 企業間・期間間・基準間の比較可能性を保証しない  
- 投資助言をしない / 金融庁公式ではない  

## ライセンス・引用

Apache License 2.0（[LICENSE](LICENSE)）。研究利用は [CITATION.cff](CITATION.cff)。  
詳細・βコーパス・英語ドキュメントは [README.md](README.md) を参照。
