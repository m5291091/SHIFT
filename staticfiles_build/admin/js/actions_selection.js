
(function($) {
    $(document).ready(function() {
        // 全選択チェックボックスを追加
        var selectAllCheckbox = $('<input type="checkbox" id="action-toggle-all">');
        $('th.action-checkbox-column').html(selectAllCheckbox);

        // 全選択チェックボックスのクリックイベント
        selectAllCheckbox.on('click', function() {
            var isChecked = $(this).is(':checked');
            $('.action-select').prop('checked', isChecked);
        });

        // 個々のチェックボックスのクリックイベント
        $('.action-select').on('click', function() {
            if (!$(this).is(':checked')) {
                selectAllCheckbox.prop('checked', false);
            } else {
                // すべてのチェックボックスが選択されているか確認
                if ($('.action-select:checked').length === $('.action-select').length) {
                    selectAllCheckbox.prop('checked', true);
                }
            }
        });
    });
})(django.jQuery);
