
document.addEventListener('DOMContentLoaded', function() {
    var fieldset = document.querySelector('.form-row.field-is_monday').closest('fieldset');
    if (!fieldset) return;

    var container = document.createElement('div');
    container.className = 'daygroup-helpers';
    container.style.marginBottom = '10px';

    var buttons = [
        {text: 'すべて選択', days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']},
        {text: '平日を選択', days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']},
        {text: '週末を選択', days: ['saturday', 'sunday']},
        {text: '選択解除', days: []}
    ];

    buttons.forEach(function(btnInfo) {
        var button = document.createElement('button');
        button.type = 'button';
        button.textContent = btnInfo.text;
        button.className = 'button';
        button.style.marginRight = '5px';
        button.addEventListener('click', function() {
            var allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
            allDays.forEach(function(day) {
                var checkbox = document.getElementById('id_is_' + day);
                if (checkbox) {
                    checkbox.checked = btnInfo.days.includes(day);
                }
            });
        });
        container.appendChild(button);
    });

    fieldset.insertBefore(container, fieldset.firstChild);
});
