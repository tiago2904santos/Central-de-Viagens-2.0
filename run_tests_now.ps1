Set-Location "c:\Users\tiago\OneDrive\Área de Trabalho\central de viagens 2.0"
$env:DJANGO_SETTINGS_MODULE = "config.settings"
python manage.py test eventos.tests.test_eventos.OficioDocumentosTest eventos.tests.test_eventos.OficioGeracaoDocumentoCorrecoesTest eventos.tests.test_eventos.OficioWizardTest eventos.tests.test_eventos.OficioStep1AcceptanceTest eventos.tests.test_eventos.OficioJustificativaTest eventos.tests.test_eventos.OficioStep1AjustesFinosTest eventos.tests.test_eventos.OficioStep1ProtocolRegressionTest -v 1 2>&1 | Out-File -FilePath "test_results.txt" -Encoding UTF8
Get-Content "test_results.txt"
