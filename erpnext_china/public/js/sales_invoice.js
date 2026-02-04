frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // 使用 setTimeout 是因为 ERPNext 的按钮是动态渲染的
        // 必须等核心代码渲染完，我们才能抓取到 DOM
        setTimeout(() => {
            // 定位：在“创建”按钮组下，寻找 data-label 为“付款”的选项
            // 使用 decodeURIComponent 是为了增强可读性，也可以直接用 data-label="付款"
            $(`.inner-group-button[data-label='${encodeURIComponent("创建")}']`)
                .find(`.dropdown-item[data-label='${encodeURIComponent("付款")}']`)
                .text(__('收款'));
        }, 200); 
    }
});