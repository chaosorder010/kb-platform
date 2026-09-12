from typing import  List
from knowledge.utils.client.ai_clients import BGEM3EmbeddingFunction


def generate_bge_m3_hybrid_vectors(model: BGEM3EmbeddingFunction, embedding_documents: List[str]):
    """
    为文本生成混合向量嵌入（稠密 + 稀疏）
    Args:
        embedding_model: BGE-M3嵌入模型
        embedding_documents: 要生成嵌入的文本列表
    Returns:
        {"dense": [...], "sparse": [...]}
    Raises:
        ValueError: 输入参数无效
        RuntimeError: 嵌入生成失败
    """
    # 1. 参数校验
    if not embedding_documents:
        raise ValueError("embedding_documents 不能为空")

    if not all(isinstance(doc, str) and doc.strip() for doc in embedding_documents):
        raise ValueError("embedding_documents 中存在无效元素（空字符串或非字符串类型）")


    # 2. 生成嵌入
    try:
        embedding_result = model.encode_documents(embedding_documents)
        dense_vecs = embedding_result['dense']
        sparse_mat = embedding_result['sparse']
        doc_count = len(embedding_documents)
        print(f"稠密向量维度：{dense_vecs.shape} # ({doc_count} 个文档, 每文档{dense_vecs.shape[1]} 维)")
        print(f"稀疏向量： 词汇表大小{sparse_mat.shape[1]}, 共 {sparse_mat.nnz} 个非零值， 每文档约 {sparse_mat.nnz // doc_count} 个")
    except Exception as e:
        raise RuntimeError(f"BGE-M3 嵌入生成失败: {e}") from e

    # 3. 校验嵌入结果
    if 'dense' not in embedding_result or 'sparse' not in embedding_result:
        raise RuntimeError(f"嵌入结果缺少必要字段，实际返回: {list(embedding_result.keys())}")

    # 5. 解析稀疏向量（CSR 矩阵 → dict）
    try:
        processed_sparse = []
        csr_array = embedding_result['sparse']

        for index in range(len(embedding_documents)):
            start = csr_array.indptr[index]
            end = csr_array.indptr[index + 1]
            token_ids = csr_array.indices[start:end].tolist()
            weights = csr_array.data[start:end].tolist()
            processed_sparse.append(dict(zip(token_ids, weights)))
    except (IndexError, AttributeError) as e:
        raise RuntimeError(f"稀疏向量解析失败（CSR 矩阵结构异常）: {e}") from e

    # 6. 返回
    return {
        "dense": [den.tolist() for den in embedding_result["dense"]],
        "sparse": processed_sparse
    }