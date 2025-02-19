# Copyright (c) Microsoft. All rights reserved.

import time

import pytest

import semantic_kernel
import semantic_kernel.connectors.ai.open_ai as sk_oai
from semantic_kernel.kernel import Kernel
from semantic_kernel.planning import SequentialPlanner
from semantic_kernel.planning.sequential_planner.sequential_planner_config import (
    SequentialPlannerConfig,
)
from tests.integration.fakes.email_plugin_fake import EmailPluginFake
from tests.integration.fakes.fun_plugin_fake import FunPluginFake
from tests.integration.fakes.writer_plugin_fake import WriterPluginFake


async def retry(func, retries=3):
    min_delay = 2
    max_delay = 7
    for i in range(retries):
        try:
            result = await func()
            return result
        except Exception:
            if i == retries - 1:  # Last retry
                raise
            time.sleep(max(min(i, max_delay), min_delay))


def initialize_kernel(get_aoai_config, use_embeddings=False, use_chat_model=False):
    _, api_key, endpoint = get_aoai_config

    kernel = Kernel()
    if use_chat_model:
        kernel.add_chat_service(
            "chat_completion",
            sk_oai.AzureChatCompletion(
                deployment_name="gpt-35-turbo",
                endpoint=endpoint,
                api_key=api_key,
            ),
        )
    else:
        kernel.add_text_completion_service(
            "text_completion",
            sk_oai.AzureChatCompletion(
                deployment_name="gpt-35-turbo",
                endpoint=endpoint,
                api_key=api_key,
            ),
        )

    if use_embeddings:
        kernel.add_text_embedding_generation_service(
            "text_embedding",
            sk_oai.AzureTextEmbedding(
                deployment_name="text-embedding-ada-002",
                endpoint=endpoint,
                api_key=api_key,
            ),
        )
    return kernel


@pytest.mark.parametrize(
    "use_chat_model, prompt, expected_function, expected_plugin",
    [
        (
            False,
            "Write a joke and send it in an e-mail to Kai.",
            "SendEmail",
            "_GLOBAL_FUNCTIONS_",
        ),
        (
            True,
            "Write a joke and send it in an e-mail to Kai.",
            "SendEmail",
            "_GLOBAL_FUNCTIONS_",
        ),
    ],
)
@pytest.mark.asyncio
async def test_create_plan_function_flow(get_aoai_config, use_chat_model, prompt, expected_function, expected_plugin):
    # Arrange
    kernel = initialize_kernel(get_aoai_config, False, use_chat_model)
    kernel.import_plugin(EmailPluginFake())
    kernel.import_plugin(FunPluginFake())

    planner = SequentialPlanner(kernel)

    # Act
    plan = await planner.create_plan(prompt)

    # Assert
    assert any(step.name == expected_function and step.plugin_name == expected_plugin for step in plan._steps)


@pytest.mark.parametrize(
    "prompt, expected_function, expected_plugin, expected_default",
    [
        (
            "Write a novel outline.",
            "NovelOutline",
            "WriterPlugin",
            "<!--===ENDPART===-->",
        )
    ],
)
@pytest.mark.asyncio
@pytest.mark.xfail(
    raises=semantic_kernel.planning.planning_exception.PlanningException,
    reason="Test is known to occasionally produce unexpected results.",
)
async def test_create_plan_with_defaults(get_aoai_config, prompt, expected_function, expected_plugin, expected_default):
    # Arrange
    kernel = initialize_kernel(get_aoai_config)
    kernel.import_plugin(EmailPluginFake())
    kernel.import_plugin(WriterPluginFake(), "WriterPlugin")

    planner = SequentialPlanner(kernel)

    # Act
    plan = await retry(lambda: planner.create_plan(prompt))

    # Assert
    assert any(
        step.name == expected_function
        and step.plugin_name == expected_plugin
        and step.parameters["endMarker"] == expected_default
        for step in plan._steps
    )


@pytest.mark.parametrize(
    "prompt, expected_function, expected_plugin",
    [
        (
            "Write a poem or joke and send it in an e-mail to Kai.",
            "SendEmail",
            "_GLOBAL_FUNCTIONS_",
        )
    ],
)
@pytest.mark.asyncio
@pytest.mark.xfail(
    raises=semantic_kernel.planning.planning_exception.PlanningException,
    reason="Test is known to occasionally produce unexpected results.",
)
async def test_create_plan_goal_relevant(get_aoai_config, prompt, expected_function, expected_plugin):
    # Arrange
    kernel = initialize_kernel(get_aoai_config, use_embeddings=True)
    kernel.import_plugin(EmailPluginFake())
    kernel.import_plugin(FunPluginFake())
    kernel.import_plugin(WriterPluginFake())

    planner = SequentialPlanner(
        kernel,
        SequentialPlannerConfig(relevancy_threshold=0.65, max_relevant_functions=30),
    )

    # Act
    plan = await retry(lambda: planner.create_plan(prompt))

    # Assert
    assert any(step.name == expected_function and step.plugin_name == expected_plugin for step in plan._steps)
