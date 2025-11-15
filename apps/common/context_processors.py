# apps/common/context_processors.py
def company_context(request):
    """将公司信息添加到模板上下文"""
    return {
        'current_company': getattr(request, 'company', None),
    }