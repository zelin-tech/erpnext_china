from decimal import Decimal
import warnings


def cncurrency(value, capital=True, prefix=False, classical=None):
    """
    中文金额大写转换

    参数:
        capital:
            True  -> 大写金额（壹贰叁）
            False -> 小写金额（一二三）

        prefix:
            True  -> 人民币前缀
            False -> 无前缀

        classical:
            True  -> 元
            False -> 圆
    """

    if not isinstance(value, (Decimal, str, int)):
        warnings.warn(
            "建议使用 Decimal 或字符串避免浮点精度问题",
            UserWarning
        )

    # 默认：
    # 大写金额 -> 元
    # 小写金额 -> 圆
    if classical is None:
        classical = True if capital else False

    # 前缀
    prefix_text = "人民币" if prefix else ""

    # 小数单位
    dunit = ("角", "分")

    # 数字字符
    if capital:
        num = (
            "零", "壹", "贰", "叁", "肆",
            "伍", "陆", "柒", "捌", "玖"
        )

        iunit = [
            None, "拾", "佰", "仟",
            "万", "拾", "佰", "仟",
            "亿", "拾", "佰", "仟",
            "万", "拾", "佰", "仟"
        ]
    else:
        num = (
            "〇", "一", "二", "三", "四",
            "五", "六", "七", "八", "九"
        )

        iunit = [
            None, "十", "百", "千",
            "万", "十", "百", "千",
            "亿", "十", "百", "千",
            "万", "十", "百", "千"
        ]

    # 元 / 圆
    iunit[0] = "元" if classical else "圆"

    # 转 Decimal
    if not isinstance(value, Decimal):
        value = Decimal(str(value)).quantize(
            Decimal("0.01")
        )

    # 负数处理
    if value < 0:
        prefix_text = "负" + prefix_text
        value = -value

    s = str(value)

    if len(s) > 19:
        raise ValueError("金额太大，无法处理")

    istr, dstr = s.split(".")

    # 整数部分反转
    istr = istr[::-1]

    so = []

    # 零元
    if value == 0:
        return prefix_text + num[0] + iunit[0] + "整"

    haszero = False

    # 无小数
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

    # 无整数
    if istr == "0":

        if haszero:
            so.pop()

        so.append(prefix_text)
        so.reverse()

        return "".join(so)

    # 整数部分
    for i, n in enumerate(istr):

        n = int(n)

        # 万、亿等位
        if i % 4 == 0:

            if i == 8 and so[-1] == iunit[4]:
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

    # 前缀
    so.append(prefix_text)

    # 翻转
    so.reverse()

    return "".join(so)