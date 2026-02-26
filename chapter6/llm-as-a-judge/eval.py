import asyncio
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from deepeval.test_case import LLMTestCase
from deepeval.models import AmazonBedrockModel
from deepeval import evaluate

# Demonstrates "LLM-as-a-judge" style relevance evaluation using DeepEval
# with Amazon Bedrock as the evaluator model backend.

async def eval_relevance():
    # 評価モデルを初期化
    deepeval_model = AmazonBedrockModel(
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-west-2",
        cost_per_input_token=0.000001,
        cost_per_output_token=0.000005,
    )

    # 評価メトリクスの設定
    metric = GEval(
        name="関連性チェック",
        evaluation_steps=[
            "LLMの回答がユーザー入力に直接関係している場合、関連性は高いと判断する",
            "LLMの回答の中に、ユーザー入力に関連しない内容が含まれている場合、関連性は低いと判断する",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=deepeval_model
    )


    # テストケースの設定
    # The evaluated output should be relevant to the user input.
    test_case = LLMTestCase(
        input="今日の天気を教えてくれますか？",
        actual_output="今日の天気は晴れです。外出しやすく洗濯日和でしょう。",
    )
    # Run evaluation once and then close underlying Bedrock model resources.
    evaluate(test_cases=[test_case], metrics=[metric])
    await deepeval_model.close()


if __name__ == "__main__":
    asyncio.run(eval_relevance())
