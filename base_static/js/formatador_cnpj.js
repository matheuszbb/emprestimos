var isDeleteOrBackspace;
var timeout = null;

document.getElementById('id_cnpj').addEventListener('keydown', function(e) {
    isDeleteOrBackspace = e.key === 'Backspace' || e.key === 'Delete';
});

document.getElementById('id_cnpj').addEventListener('input', function(e) {
    var input = this;
    clearTimeout(timeout);
    timeout = setTimeout(function () {
        if (isDeleteOrBackspace) {
            return;
        }

        var start = input.selectionStart,
            end = input.selectionEnd;

        var oldVal = input.value;
        input.value = input.value.replace(/\D/g, '')
                                 .replace(/(\d{2})(\d)/, '$1.$2')
                                 .replace(/(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
                                 .replace(/(\d{2})\.(\d{3})\.(\d{3})(\d)/, '$1.$2.$3/$4')
                                 .replace(/(\d{2})\.(\d{3})\.(\d{3})\/(\d{4})(\d)/, '$1.$2.$3/$4-$5');

        var diff = input.value.length - oldVal.length;

        input.setSelectionRange(start + diff, end + diff);
    }, 500);
});
