function formatarQuantidade(input) {
    return input.toLocaleString('pt-BR');
} 

var elementos = document.getElementsByClassName('quantidade_elementos');
for (var i = 0; i < elementos.length; i++) {
    var texto = elementos[i].innerText;
    var valor = parseFloat(texto.replace(/[^0-9.,]/g, "").replace(',', '.'));
    if (!isNaN(valor)) {
        var valorFormatado = valor.toLocaleString('pt-BR');
        elementos[i].innerText = texto.replace(valor.toString(), valorFormatado);
    }
}
