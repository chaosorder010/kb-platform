"""图片理解节点

查询期多模态入口：若用户上传了图片，先用 VLM 生成图片描述并拼进 original_query，
再把图片上传到 MinIO 拿到可回溯 URL。无图时透传，不影响纯文本查询流程。
"""

import os
import io
import base64
import time
from datetime import datetime
from typing import Dict, Any, Union

from knowledge.processor.query_processor.base import BaseNode
from knowledge.processor.query_processor.state import QueryGraphState
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.prompts.query_prompt import IMAGE_UNDERSTANDING_USER_PROMPT_TEMPLATE


class ImageUnderstandingNode(BaseNode):
    """图片理解节点。

    职责：
    1. 无图片输入时直接透传 state（纯文本查询走原流程，零影响）。
    2. 有图片时：
       a. 把 base64 图片上传到 MinIO，得到可回溯的 image_url。
       b. 调用 VLM（qwen3-vl-flash）生成图片描述。
       c. 将图片描述拼进 original_query，供下游商品名确认 / 检索 / 答案生成使用。
    3. VLM 或 MinIO 任一环节失败均优雅降级（仅 warning，不阻断查询）。
    """

    name = "image_understanding_node"

    def process(self, state: QueryGraphState) -> Union[QueryGraphState, Dict[str, Any]]:
        # 1. 取图片 base64，无图则透传（纯文本查询原流程不变）
        image_base64 = state.get("image_base64") or ""
        if not image_base64:
            return state

        original_query = state.get("original_query") or ""
        image_mime = state.get("image_mime") or "image/jpeg"
        task_id = state.get("task_id") or ""

        # 2. 上传图片到 MinIO（失败降级，不阻断）
        image_url = self._upload_image_to_minio(image_base64, image_mime, task_id)
        if image_url:
            state["image_url"] = image_url

        # 3. 调 VLM 生成图片描述（失败降级）
        image_description = self._understand_image(image_base64, image_mime, original_query)
        if not image_description:
            self.logger.warning("VLM 图片理解失败，降级使用原始查询")
            return state

        state["image_description"] = image_description
        # 4. 图片描述拼进 original_query，供下游节点（商品名确认 / 检索 / 答案生成）使用
        state["original_query"] = f"{original_query}\n【图片描述】{image_description}"

        self.logger.info(f"图片理解完成，image_url={image_url}，描述长度={len(image_description)}")
        return state

    def _upload_image_to_minio(self, image_base64: str, image_mime: str, task_id: str) -> str:
        """把 base64 图片上传到 MinIO，返回可访问 URL。失败返回空串。"""
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            self.logger.warning(f"图片 base64 解码失败: {e}")
            return ""

        endpoint = os.getenv("MINIO_ENDPOINT", "")
        bucket_name = os.getenv("MINIO_BUCKET_NAME", "")
        if not endpoint or not bucket_name:
            self.logger.warning("未配置 MINIO_ENDPOINT / MINIO_BUCKET_NAME，跳过图片上传")
            return ""

        suffix = ".png" if "png" in image_mime else ".jpg"
        object_name = f"query_images/{datetime.now().strftime('%Y%m%d/%H%M%S')}_{task_id}{suffix}"

        try:
            minio_client = StorageClients.get_minio_client()
            minio_client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(image_bytes),
                len(image_bytes),
                content_type=image_mime,
            )
            # 与 upload_service 的 URL 拼装保持一致：协议 + endpoint/bucket/object
            base_url = endpoint if endpoint.startswith("http") else f"http://{endpoint}"
            image_url = f"{base_url}/{bucket_name}/{object_name}"
            self.logger.info(f"用户图片已上传 MinIO: {image_url}")
            return image_url
        except Exception as e:
            self.logger.warning(f"图片上传 MinIO 失败，降级不存图: {e}")
            return ""

    def _understand_image(self, image_base64: str, image_mime: str, original_query: str) -> str:
        """调用 VLM 生成图片描述。失败返回空串。"""
        start_time = time.time()
        vl_model = os.getenv("VL_MODEL", "")
        if not vl_model:
            self.logger.warning("未配置 VL_MODEL，跳过图片理解")
            return ""

        try:
            vlm_client = AIClients.get_vlm_client()
        except ConnectionError as e:
            self.logger.warning(f"VLM 客户端获取失败: {e}")
            return ""

        user_prompt = IMAGE_UNDERSTANDING_USER_PROMPT_TEMPLATE.format(original_query=original_query)

        try:
            # 调用写法参照 import_processor/nodes/md_to_img_node.py 的 _summary_one
            resp = vlm_client.chat.completions.create(
                model=vl_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{image_mime};base64,{image_base64}"}},
                    ],
                }],
            )
            description = (resp.choices[0].message.content or "").strip()
            self.logger.info(f"VLM 图片理解耗时 {round(time.time() - start_time, 2)}s")
            return description
        except Exception as e:
            self.logger.warning(f"VLM 图片理解调用失败: {e}")
            return ""


if __name__ == "__main__":
    import json

    node = ImageUnderstandingNode()
    # 手动测试：读取一张本地图片转 base64 后填入
    # with open("test.jpg", "rb") as f:
    #     img_b64 = base64.b64encode(f.read()).decode("utf-8")
    # init_state = {
    #     "original_query": "这个设备怎么用？",
    #     "image_base64": img_b64,
    #     "image_mime": "image/jpeg",
    #     "task_id": "test_img_001",
    # }
    # result = node.process(init_state)
    # print(json.dumps(
    #     {k: result.get(k) for k in ("original_query", "image_url", "image_description")},
    #     ensure_ascii=False, indent=2))
    print("ImageUnderstandingNode 节点定义完成，取消注释 __main__ 内代码可手动测试")
