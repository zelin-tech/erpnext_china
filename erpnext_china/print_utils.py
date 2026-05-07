from decimal import Decimal
import json
import warnings

import frappe
from frappe.utils.data import flt


def get_owner_username(doc):
    return frappe.db.get_value("User", doc.owner, "full_name")


def get_submit_username(doc):
    """获取提交人姓名。"""
    filters = {
        "ref_doctype": doc.doctype,
        "docname": doc.name,
        "data": ("like", "%docstatus%"),
    }

    version_list = frappe.get_all(
        "Version",
        filters=filters,
        fields=["owner", "data"],
        order_by="creation desc",
    )

    for version in version_list:
        data = json.loads(version.data or "{}")
        found = [
            f for f in data.get("changed", [])
            if f[0] == "docstatus" and f[-1] == 1
        ]
        if found:
            return frappe.db.get_value("User", version.owner, "full_name")

    if doc.docstatus == 1 and doc.modified_by:
        return frappe.db.get_value("User", doc.modified_by, "full_name")


def money_in_words(number, main_currency=None, fraction_currency=None):
    """
    中文金额大写入口。

    注意：
    这个函数不会自动覆盖 frappe.utils.money_in_words。
    建议在 hooks.py 的 jinja.methods 或 doc_events 中显式调用。
    """
    return cn_money_in_words(number, main_currency)


def cn_money_in_words(number, currency=None):
    """
    金额转中文大写金额。

    示例：
    1234.56 -> 人民币壹仟贰佰叁拾肆元伍角陆分
    1234.00 -> 人民币壹仟贰佰叁拾肆元整
    """
    if number is None:
        return ""

    try:
        value = Decimal(str(number)).quantize(Decimal("0.01"))
    except Exception:
        return ""

    if currency in ("CNY", "RMB", "人民币", None, ""):
        return cncurrency(value, capital=True, prefix_text=True, classical=True)

    return f"{currency}{cncurrency(value, capital=True, prefix_text=False, classical=True)}"


def cncurrency(value, capital=True, prefix_text=False, classical=None):
    """
    金额转中文大写。

    参数：
    capital:
        True  -> 大写汉字金额：壹贰叁
        False -> 普通汉字金额：一二三

    classical:
        True  -> 使用“元”
        False -> 使用“圆”

    prefix_text:
        True  -> 前缀加“人民币”
        False -> 不加前缀
    """
    if not isinstance(value, (Decimal, str, int)):
        warnings.warn(
            "由于浮点数精度问题，请考虑使用字符串或 Decimal。",
            UserWarning,
        )

    if classical is None:
        classical = True if capital else False

    prefix = "人民币" if prefix_text else ""

    dunit = ("角", "分")

    if capital:
        num = ("零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖")
        iunit = [
            None, "拾", "佰", "仟",
            "万", "拾", "佰", "仟",
            "亿", "拾", "佰", "仟",
            "万", "拾", "佰", "仟",
        ]
    else:
        num = ("〇", "一", "二", "三", "四", "五", "六", "七", "八", "九")
        iunit = [
            None, "十", "百", "千",
            "万", "十", "百", "千",
            "亿", "十", "百", "千",
            "万", "十", "百", "千",
        ]

    iunit[0] = "元" if classical else "圆"

    if not isinstance(value, Decimal):
        value = Decimal(str(value)).quantize(Decimal("0.01"))

    if value < 0:
        prefix += "负"
        value = -value

    s = str(value.quantize(Decimal("0.01")))

    if len(s) > 19:
        raise ValueError("金额太大了，不知道该怎么表达。")

    istr, dstr = s.split(".")
    istr = istr[::-1]

    so = []

    if value == 0:
        return prefix + num[0] + iunit[0] + "整"

    haszero = False

    if dstr == "00":
        haszero = True

    # 分
    if dstr[1] != "0":
        so.append(dunit[1])
        so.append(num[int(dstr[1])])
    else:
        so.append("整")

    # 角
    if dstr[0] != "0":
        so.append(dunit[0])
        so.append(num[int(dstr[0])])
    elif dstr[1] != "0":
        so.append(num[0])
        haszero = True

    # 无整数部分，例如 0.56
    if istr == "0":
        if haszero and so:
            so.pop()
        so.append(prefix)
        so.reverse()
        return "".join(so)

    # 整数部分
    for i, n in enumerate(istr):
        n = int(n)

        if i >= len(iunit):
            raise ValueError("金额太大了，不知道该怎么表达。")

        if i % 4 == 0:
            if i == 8 and so and so[-1] == iunit[4]:
                so.pop()

            so.append(iunit[i])

            if n == 0:
                if not haszero:
                    so.insert(-1, num[0])
                    haszero = True
            else:
                so.append(num[n])
                haszero = False
        else:
            if n != 0:
                so.append(iunit[i])
                so.append(num[n])
                haszero = False
            else:
                if not haszero:
                    so.append(num[0])
                    haszero = True

    so.append(prefix)
    so.reverse()

    return "".join(so)


def set_chinese_in_words(doc, method=None):
    """
    在单据保存/提交前重写 in_words 和 base_in_words。

    建议在 hooks.py 的 doc_events 中调用。
    """
    if not (frappe.local.lang or "").startswith("zh"):
        return

    if doc.meta.get_field("base_in_words"):
        base_amount = _get_doc_amount(
            doc,
            rounded_field="base_rounded_total",
            total_field="base_grand_total",
        )
        doc.base_in_words = cn_money_in_words(
            abs(base_amount),
            doc.get("company_currency"),
        )

    if doc.meta.get_field("in_words"):
        amount = _get_doc_amount(
            doc,
            rounded_field="rounded_total",
            total_field="grand_total",
        )
        doc.in_words = cn_money_in_words(
            abs(amount),
            doc.get("currency"),
        )


def _get_doc_amount(doc, rounded_field, total_field):
    """
    优先使用 rounded_total；
    如果单据禁用了 rounded total，则使用 grand_total。
    """
    use_rounded = (
        doc.meta.get_field(rounded_field)
        and not _is_rounded_total_disabled(doc)
        and doc.get(rounded_field) is not None
    )

    if use_rounded:
        return flt(doc.get(rounded_field))

    return flt(doc.get(total_field))


def _is_rounded_total_disabled(doc):
    return (
        hasattr(doc, "is_rounded_total_disabled")
        and doc.is_rounded_total_disabled()
    )