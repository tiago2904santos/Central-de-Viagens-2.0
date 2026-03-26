(function () {
  async function calcularDiariasEngine(params) {
    const payload = {
      data_saida: params && params.data_saida ? params.data_saida : null,
      hora_saida: params && params.hora_saida ? params.hora_saida : null,
      data_retorno: params && params.data_retorno ? params.data_retorno : null,
      hora_retorno: params && params.hora_retorno ? params.hora_retorno : null,
      pessoas: Number(params && params.pessoas ? params.pessoas : 0),
      valor: Number(params && params.valor ? params.valor : 0),
    };

    console.log('PAYLOAD DIARIAS:', payload);

    if (!payload.data_saida || !payload.hora_saida || !payload.data_retorno || !payload.hora_retorno) {
      const emptyResult = { qtd_diarias: 0, valor_total: 0, valor_extenso: '' };
      console.log('RESULT DIARIAS:', emptyResult);
      return emptyResult;
    }

    const response = await fetch(params.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': params.csrfToken || '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok || (data && data.success === false)) {
      throw new Error((data && data.error) || 'Erro ao calcular as diárias.');
    }

    const result = {
      qtd_diarias: Number(String((data && (data.qtd_diarias || data.quantidade_diarias)) || '0').replace(',', '.')) || 0,
      valor_total: Number(String((data && data.valor_total) || '0').replace(/\./g, '').replace(',', '.')) || 0,
      valor_extenso: (data && data.valor_extenso) || '',
    };

    console.log('RESULT DIARIAS:', result);
    return result;
  }

  window.calcularDiariasEngine = calcularDiariasEngine;
})();
