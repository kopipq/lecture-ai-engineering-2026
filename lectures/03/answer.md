# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：「AIE2026の講座で使う「lecNN-start タグ」とは何ですか？」を両方に聞いた。`app.ask` は「NN」をニューラルネットワークと推測し、「ニューラルネットワークの基礎を学ぶセクションの開始位置を示す目印である可能性が非常に高い」と誤った内容を答えた。エージェントは `search_glossary` で用語集を引き、「各回の演習開始時点のコードに付けた Git タグで、例は `lec03-start`」と正しく答え、関係する回として第1回を示した。講座に固有の言葉は、モデルの知識にないので、ツールで調べられるかどうかで正誤が分かれる。
- `--trace` で見えたツール呼び出し（ツール名と引数）：

  ```
  # "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？"
  [tool call]   search_glossary({'query': 'lecNN-start タグ'})

  # "LoRAとQLoRAの違いは？"
  [tool call]   search_glossary({'query': 'LoRA'})
  [tool call]   search_glossary({'query': 'QLoRA'})

  # "第2回の内容から確認問題を1問出して"
  [tool call]   make_quiz({'lecture': 2})
  ```

  LoRA と QLoRA の質問では、docstring の「query には調べたい用語を1つだけ入れる」に従い、用語ごとに1回ずつ、2回の検索を1回の応答の中でまとめて呼んでいた。
- 1つの質問での LLM 呼び出し回数（`requests`）：上の3つの質問はどれも `requests=2` だった。1回目でツールを呼び、2回目でツールの結果をもとに回答を作る。LoRA と QLoRA の質問は検索が2回あったが、2つの呼び出しが同じ応答に入っていたので、`requests` は増えなかった。
- 追加したツールと、docstring に書いた説明：`make_quiz(lecture: int)` を追加した。指定した回の用語を用語集からランダムに1つ選び、「〇〇とはどういう意味ですか？」という問題と、用語集の定義を答えとして JSON で返す。docstring には、何を返すか、「第2回の内容から確認問題を出して」のように復習用の問題を求められたときに使うこと、答えは利用者が考えたあとに示すこと、の3点を書いた。実行すると、ツールは「エポック」の問題と答えを返したが、モデルは答えを出さずに問題だけを示し、「答えが分かったら教えてください」と返した。docstring の最後の1文がモデルの振る舞いに効いている。ただし今の CLI は1回の質問で終わるので、利用者が答えを返す続きの会話ができず、答えを確認する手段がない。

## 宿題

- 取り組んだレベル：実装
- やったこと：
  - `app/tools.py` に `save_learning_log(title, content)` を追加した。本文を `learning_log/YYYYMMDD-HHMMSS.md` に Markdown で保存する。ファイル名はモデルの引数ではなく日時から作るので、モデルが `learning_log/` の外に書き込むことはできない。同じ秒に2回保存したときは連番を付け、既存のファイルは上書きしない。本文が空のときと 10,000 文字を超えるときは、保存せずに理由を返す。
  - `app/agent.py` で `requires_approval=True` を付けて登録し、エージェントの `output_type` を `[str, DeferredToolRequests]` にした。
  - CLI に `run_with_approval` を追加した。結果が `DeferredToolRequests` だったら、ツール名と引数を表示して `y/N` で確認する。答えを `build_results` で `DeferredToolResults` にし、それまでの `message_history` と `usage` と一緒に渡して続きを実行する。拒否したときは `ToolDenied` で「利用者が実行を許可しませんでした」とモデルに返す。標準入力が閉じていて答えられないときは拒否として扱う。
  - TestModel を使ったテストを `tests/test_learning_log.py` に書いた。どのテストも本物の `learning_log/` に書き込まないよう、保存先を一時フォルダに差し替える fixture を `tests/conftest.py` に置いた。承認待ちのツールは承認されるまで結果を返さないので、既存の `test_base_tools_are_registered_and_called` は、承認待ちの呼び出しの数を差し引いて比べるように直した。
- 結果：
  - `uv run pytest -q` で 27 件すべて通った。テストで確かめたことは次のとおり。
    - モデルが `save_learning_log` を呼ぶと、回答ではなく `DeferredToolRequests` が返り、その時点ではファイルが作られない
    - 承認すると1件だけ保存され、ツールの結果「保存しました」がモデルに戻る
    - 拒否するとファイルは作られず、拒否の文面がツールの結果としてモデルに戻る
    - `y` と `yes` だけを承認とみなし、空入力と入力なしは拒否になる
  - TestModel で CLI の流れを通したときの表示（`y` を入力した場合）：

    ```
    [approval] save_learning_log を実行しようとしています。
      title: a
      content: a
    実行してよいですか？ [y/N]: y
    {"save_learning_log":"learning_log/20261109-154805.md に保存しました。"}

    --- trace ---
    [tool call]   save_learning_log({'title': 'a', 'content': 'a'})
    [tool return] save_learning_log -> learning_log/20261109-154805.md に保存しました。…
    [usage] RunUsage(input_tokens=105, output_tokens=20, requests=2, tool_calls=1)
    ```

  - 実モデル（gemini-3.5-flash-lite）での実行：`uv run --env-file .env python -m app.agent --trace "LoRAの要点を調べて、学習ログに保存して"`
    - 承認した場合：モデルはまず `search_glossary` で用語集を引き、その定義をもとに `save_learning_log` を呼んだ。そこで実行が止まって確認が表示され、`y` と答えると `learning_log/20261109-164025.md` が作られた。`requests=3` の内訳は、`search_glossary` を呼ぶ応答、`save_learning_log` を呼んで承認待ちになる応答、承認後に最終回答を作る応答の3回である。

      ```
      [approval] save_learning_log を実行しようとしています。
        content: ## LoRAの要点
          - 定義: 事前学習済みの重みを固定したまま、重みの更新分を2つの小さな行列の積（低ランク行列）で表し、その小さな行列だけを学習するPEFT（Parameter-Efficient Fine-Tuning）手法。
          - 特徴: 学習するパラメータが非常に少なく、学習結果（アダプタ）も小さいファイルサイズで保存できる。
          - 関連する回: 第2回
        title: LoRAの要点についての学習記録
      実行してよいですか？ [y/N]: y
      LoRAの要点について講座の用語集を確認し、学習ログとして保存しました。
      （回答本文は省略）

      --- trace ---
      [tool call]   search_glossary({'query': 'LoRA'})
      [tool return] search_glossary -> [{"term": "LoRA", "lecture": 2, "definition": "事前学習済みの重みは固定したまま、…
      [tool call]   save_learning_log({'content': '## LoRAの要点\n- 定義: …', 'title': 'LoRAの要点についての学習記録'})
      [tool return] save_learning_log -> learning_log/20261109-164025.md に保存しました。…
      [usage] RunUsage(…, input_tokens=2464, output_tokens=275, requests=3, tool_calls=2)
      ```

    - 拒否した場合：同じコマンドで `n` と答えた。`learning_log/` のファイルは承認した回の1件のままで、新しいファイルは作られなかった。拒否の文面はツールの結果としてモデルに戻り、モデルは「利用者の確認が得られなかったため、学習ログの保存は行っていません」と伝えたうえで、調べた要点を画面にだけ示した。保存を呼び直すことはなかった。`tool_calls=1` で、拒否した `save_learning_log` は実行したツールの数に入らない。

      ```
      実行してよいですか？ [y/N]: n
      利用者の確認が得られなかったため、学習ログの保存は行っていません。
      （回答本文は省略）

      --- trace ---
      [tool call]   search_glossary({'query': 'LoRA'})
      [tool return] search_glossary -> [{"term": "LoRA", "lecture": 2, "definition": "事前学習済みの重みは固定したまま、…
      [tool call]   save_learning_log({'title': 'LoRAの要点', 'content': '### LoRA（Low-Rank Adaptation）の要点\n\n- **定義**: …'})
      [tool return] save_learning_log -> 利用者が実行を許可しませんでした。実行していないことを利用者に伝えてください。…
      [usage] RunUsage(…, input_tokens=2496, output_tokens=329, requests=3, tool_calls=1)
      ```

    - 同じ質問でも、モデルが作る `title` と `content` は2回で異なっていた。2回目は、用語集の `related` 欄から関連用語を加えたうえで、用語集の定義にない「メモリや計算コストを抑えられる」という説明も足していた。保存される内容はその都度変わるので、承認の画面で中身を読んでから答える意味がある。
- 気づき・疑問：
  - 承認を挟むと、1つの質問が「承認待ちで止まる実行」と「承認結果を渡して続ける実行」の2回に分かれる。続きの実行に `message_history` を渡さないと、モデルは自分が何を呼んだかを知らない。`usage` も引き継がないと、`--trace` の `requests` が2回目の実行分だけになる。
  - 承認待ちのツールは結果を返さないまま実行が終わる。そのため「呼んだツールはすべて結果を返す」という前提のテストが壊れた。承認を入れると、テストで確かめるべき性質も変わる。
  - 疑問：今の CLI は「保存する／しない」の二択しかない。Pydantic AI の `ToolApproved(override_args=...)` を使えば、利用者が本文を直してから保存することもできそうだ。どこまで利用者に編集させるのがよいか。
  <!-- TODO: 実モデルで動かして気づいたことを、自分の言葉で足す -->
