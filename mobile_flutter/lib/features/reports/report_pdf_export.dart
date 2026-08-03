import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

Future<void> exportContractExpiryPdf({
  required List<Map<String, dynamic>> rows,
  required int windowDays,
  bool moreThanFiftyDays = false,
}) async {
  final periodLabel = moreThanFiftyDays
      ? 'with more than 50 days remaining'
      : 'expiring within $windowDays days';
  final document = pw.Document(
    title: 'Contracts $periodLabel',
    author: 'Rail Inspect',
  );
  final generatedAt = DateFormat('dd MMM yyyy, HH:mm').format(DateTime.now());
  const headerStyle = pw.TextStyle(
    fontSize: 9,
    fontWeight: pw.FontWeight.bold,
    color: PdfColors.white,
  );

  document.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(28),
      header: (_) => pw.Container(
        padding: const pw.EdgeInsets.only(bottom: 10),
        decoration: const pw.BoxDecoration(
          border: pw.Border(
            bottom: pw.BorderSide(color: PdfColors.blueGrey200),
          ),
        ),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(
              'RAIL INSPECT',
              style: const pw.TextStyle(
                color: PdfColors.blue800,
                fontSize: 10,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
            pw.Text('Generated $generatedAt',
                style: const pw.TextStyle(
                    fontSize: 8, color: PdfColors.blueGrey600)),
          ],
        ),
      ),
      footer: (context) => pw.Align(
        alignment: pw.Alignment.centerRight,
        child: pw.Text(
          'Page ${context.pageNumber} of ${context.pagesCount}',
          style: const pw.TextStyle(fontSize: 8, color: PdfColors.blueGrey600),
        ),
      ),
      build: (_) => [
        pw.SizedBox(height: 16),
        pw.Text(
          'Contract Validity Watch',
          style:
              const pw.TextStyle(fontSize: 22, fontWeight: pw.FontWeight.bold),
        ),
        pw.SizedBox(height: 4),
        pw.Text(
          '${rows.length} contracts $periodLabel',
          style: const pw.TextStyle(fontSize: 11, color: PdfColors.blueGrey700),
        ),
        pw.SizedBox(height: 18),
        if (rows.isEmpty)
          pw.Container(
            width: double.infinity,
            padding: const pw.EdgeInsets.all(18),
            decoration: pw.BoxDecoration(
              color: PdfColors.blueGrey50,
              borderRadius: pw.BorderRadius.circular(8),
            ),
            child: pw.Text('No contracts expire within the selected period.'),
          )
        else
          pw.TableHelper.fromTextArray(
            headers: const [
              'Code',
              'Contract',
              'Station',
              'Valid till',
              'Days',
              'Risk',
            ],
            data: rows
                .map((row) => [
                      '${row['contract_code'] ?? '-'}',
                      '${row['contract_name'] ?? 'Contract'}',
                      '${row['station_code'] ?? '-'}',
                      _formatDate(row['valid_to']),
                      '${row['days_remaining'] ?? ''}',
                      _riskLabel(row['days_remaining']),
                    ])
                .toList(),
            headerDecoration: const pw.BoxDecoration(color: PdfColors.blue800),
            headerStyle: headerStyle,
            cellStyle: const pw.TextStyle(fontSize: 8.5),
            cellPadding:
                const pw.EdgeInsets.symmetric(horizontal: 7, vertical: 7),
            columnWidths: const {
              0: pw.FlexColumnWidth(0.8),
              1: pw.FlexColumnWidth(2.2),
              2: pw.FlexColumnWidth(0.75),
              3: pw.FlexColumnWidth(1),
              4: pw.FixedColumnWidth(34),
              5: pw.FixedColumnWidth(48),
            },
            border:
                pw.TableBorder.all(color: PdfColors.blueGrey100, width: 0.5),
            oddRowDecoration:
                const pw.BoxDecoration(color: PdfColors.blueGrey50),
          ),
      ],
    ),
  );

  await Printing.sharePdf(
    bytes: await document.save(),
    filename: moreThanFiftyDays
        ? 'contract-validity-50-plus-days.pdf'
        : 'contract-expiry-$windowDays-days.pdf',
  );
}

String _formatDate(Object? value) {
  final date = DateTime.tryParse('${value ?? ''}');
  return date == null ? '-' : DateFormat('dd MMM yyyy').format(date);
}

String _riskLabel(Object? value) {
  final days = value is num ? value.toInt() : int.tryParse('$value');
  if (days == null) return 'Unknown';
  if (days < 0) return 'Expired';
  if (days <= 10) return 'Critical';
  if (days <= 30) return 'Attention';
  return 'Active';
}
