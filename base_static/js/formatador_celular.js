var isDeleteOrBackspace;
var timeout = null;

document.getElementById('id_tipo').addEventListener('change', function(e) {
    phoneType = this.value;
});

document.getElementById('id_contato').addEventListener('keydown', function(e) {
    isDeleteOrBackspace = e.key === 'Backspace' || e.key === 'Delete';
});

document.getElementById('id_contato').addEventListener('input', function(e) {
    var input = this;
    clearTimeout(timeout);
    timeout = setTimeout(function () {
        var phoneType = document.getElementById('id_tipo').value;
        if (phoneType !== 'celular' && phoneType !== 'whatsapp') {
            return;
        }

        if (isDeleteOrBackspace) {
            return;
        }

        var start = input.selectionStart,
            end = input.selectionEnd;

        var oldVal = input.value;
        input.value = input.value.replace(/\D/g, '');

        var digitCount = input.value.length;

        if(digitCount === 13) {
            input.value = input.value.replace(/^(\d{2})(\d{2})(\d{1})(\d{4})(\d{4})$/, '+$1 ($2) $3$4-$5');
        } else if(digitCount === 12) {
            input.value = input.value.replace(/^(\d{2})(\d{2})(\d{4})(\d{4})$/, '+$1 ($2) $3-$4');
        } else if(digitCount === 11) {
            input.value = input.value.replace(/^(\d{2})(\d{1})(\d{4})(\d{4})$/, '($1) $2$3-$4');
        } else if(digitCount === 10) {
            input.value = input.value.replace(/^(\d{2})(\d{4})(\d{4})$/, '($1) $2-$3');
        }

        var diff = input.value.length - oldVal.length;

        input.setSelectionRange(start + diff, end + diff);
    }, 500);
});