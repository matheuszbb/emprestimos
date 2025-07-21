function formatarComoMoeda(numero) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numero);
}

var elementos = document.getElementsByClassName('valor_monetario');

for (var i = 0; i < elementos.length; i++) {
  var texto = elementos[i].innerText;
  var valor = parseFloat(texto.replace(/[^0-9.,]/g, "").replace(',', '.'));
  var textoSemValor = texto.replace(/[\d.,]/g, '');
  textoSemValor = textoSemValor.replace('R$', '');

  if (!isNaN(valor) && !texto.includes('R$')) {
    elementos[i].innerText = textoSemValor + formatarComoMoeda(valor);
  }
}
