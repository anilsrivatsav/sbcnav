import 'dart:io';

import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:sqflite/sqflite.dart';

Future<void> exportContractsPdf(
    {required List<Map<String, dynamic>> rows, required String family}) async {
  final document = pw.Document(
      title: '${family == 'catering' ? 'Catering' : 'Publicity'} Contracts');
  document.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4.landscape,
    build: (_) => [
      pw.Text('${family == 'catering' ? 'Catering' : 'Publicity'} Contracts',
          style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold)),
      pw.SizedBox(height: 12),
      pw.Table.fromTextArray(
        headers: const [
          'Contract',
          'Reference / Unit',
          'Policy / Type',
          'Status',
          'Value'
        ],
        data: rows
            .map((row) => [
                  '${row['contract_name'] ?? row['licensee_name'] ?? 'Unnamed'}',
                  '${row['contract_number'] ?? row['unit_no'] ?? '—'}',
                  '${row['policy_code'] ?? row['type_of_unit'] ?? '—'}',
                  '${row['status'] ?? row['unit_status'] ?? '—'}',
                  '${(row['financials'] is Map ? (row['financials'] as Map)['total_contract_value'] : row['license_fee']) ?? 0}',
                ])
            .toList(),
      ),
    ],
  ));
  await Printing.sharePdf(
      bytes: await document.save(),
      filename: 'contracts-${family.toLowerCase()}.pdf');
}

Future<void> exportInspectionPdf({
  required Map<String, dynamic> inspection,
  required Map<String, dynamic> template,
  required List<Map<String, dynamic>> responses,
  required List<Map<String, dynamic>> findings,
  required List<Map<String, dynamic>> evidence,
  required List<Map<String, dynamic>> notes,
}) async {
  final responseByQuestion = {
    for (final response in responses) '${response['question_code']}': response,
  };
  final definition = template['definition'] is Map
      ? Map<String, dynamic>.from(template['definition'] as Map)
      : template;
  final sections = (definition['sections'] as List? ?? const [])
      .map((section) => Map<String, dynamic>.from(section as Map))
      .toList();
  final generatedAt = DateFormat('dd MMM yyyy, HH:mm').format(DateTime.now());
  final station = '${inspection['station_code'] ?? 'Unknown station'}';
  final inspectionId = '${inspection['inspection_id'] ?? ''}';
  final fileName = _safePdfFileName(
    'inspection-$station-${inspectionId.isEmpty ? DateTime.now().millisecondsSinceEpoch : inspectionId}.pdf',
  );
  final document = pw.Document(
    title: 'Station Inspection - $station',
    author: 'Rail Inspect',
  );

  final passed =
      responses.where((row) => '${row['response_value']}' == 'pass').length;
  final failed =
      responses.where((row) => '${row['response_value']}' == 'fail').length;
  final unanswered = sections.fold<int>(0, (total, section) {
    final questions = section['questions'] as List? ?? const [];
    return total +
        questions.where((question) {
          final code = '${(question as Map)['code']}';
          return !responseByQuestion.containsKey(code);
        }).length;
  });

  document.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.fromLTRB(30, 28, 30, 32),
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
              style: pw.TextStyle(
                color: PdfColors.blue800,
                fontSize: 10,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
            pw.Text(
              'Generated $generatedAt',
              style: const pw.TextStyle(
                fontSize: 8,
                color: PdfColors.blueGrey600,
              ),
            ),
          ],
        ),
      ),
      footer: (context) => pw.Align(
        alignment: pw.Alignment.centerRight,
        child: pw.Text(
          'Page ${context.pageNumber} of ${context.pagesCount}',
          style: const pw.TextStyle(
            fontSize: 8,
            color: PdfColors.blueGrey600,
          ),
        ),
      ),
      build: (_) => [
        pw.SizedBox(height: 16),
        pw.Text(
          'Station Inspection Report',
          style: pw.TextStyle(
            fontSize: 22,
            fontWeight: pw.FontWeight.bold,
            color: PdfColors.blueGrey900,
          ),
        ),
        pw.SizedBox(height: 5),
        pw.Text(
          '${definition['name'] ?? 'Commercial inspection'} | $station',
          style: const pw.TextStyle(fontSize: 11, color: PdfColors.blueGrey700),
        ),
        pw.SizedBox(height: 14),
        pw.Container(
          padding: const pw.EdgeInsets.all(12),
          decoration: pw.BoxDecoration(
            color: PdfColors.blueGrey50,
            borderRadius: pw.BorderRadius.circular(8),
          ),
          child: pw.Wrap(
            spacing: 18,
            runSpacing: 8,
            children: [
              _pdfMeta('Inspector', inspection['inspector_name']),
              _pdfMeta('Type', inspection['inspection_type']),
              _pdfMeta('Status', inspection['status']),
              _pdfMeta(
                  'Started', _formatInspectionDate(inspection['started_at'])),
              _pdfMeta('Completed',
                  _formatInspectionDate(inspection['completed_at'])),
              _pdfMeta('Score', '${inspection['score'] ?? 0}%'),
            ],
          ),
        ),
        pw.SizedBox(height: 14),
        pw.Row(
          children: [
            _pdfKpi('Passed', '$passed', PdfColors.green700),
            _pdfKpi('Failed', '$failed', PdfColors.red700),
            _pdfKpi('Unanswered', '$unanswered', PdfColors.orange700),
            _pdfKpi('Photos', '${evidence.length}', PdfColors.blue700),
            _pdfKpi('Notes', '${notes.length}', PdfColors.purple700),
          ],
        ),
        if ('${inspection['remarks'] ?? ''}'.trim().isNotEmpty) ...[
          pw.SizedBox(height: 14),
          _pdfSectionTitle('Overall remarks'),
          pw.Text('${inspection['remarks']}'),
        ],
        pw.SizedBox(height: 18),
        _pdfSectionTitle('Checklist responses'),
        for (final section in sections) ...[
          pw.SizedBox(height: 10),
          pw.Text(
            '${section['title'] ?? 'Section'}',
            style: pw.TextStyle(
              fontSize: 12,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.blue800,
            ),
          ),
          pw.SizedBox(height: 5),
          _responseTable(section, responseByQuestion),
        ],
        if (findings.isNotEmpty) ...[
          pw.SizedBox(height: 18),
          _pdfSectionTitle('Deficiencies and action points'),
          pw.SizedBox(height: 7),
          pw.TableHelper.fromTextArray(
            headers: const [
              'Item',
              'Severity',
              'Status',
              'Target date',
              'Description'
            ],
            data: findings
                .map((row) => [
                      '${row['title'] ?? '-'}',
                      '${row['severity'] ?? '-'}',
                      '${row['status'] ?? '-'}',
                      '${row['target_date'] ?? '-'}',
                      '${row['description'] ?? '-'}',
                    ])
                .toList(),
            headerDecoration: const pw.BoxDecoration(color: PdfColors.red700),
            headerStyle: pw.TextStyle(
              color: PdfColors.white,
              fontSize: 8,
              fontWeight: pw.FontWeight.bold,
            ),
            cellStyle: const pw.TextStyle(fontSize: 7.5),
            cellPadding: const pw.EdgeInsets.all(5),
            border:
                pw.TableBorder.all(color: PdfColors.blueGrey100, width: 0.5),
          ),
        ],
        if (notes.isNotEmpty) ...[
          pw.SizedBox(height: 18),
          _pdfSectionTitle('Inspection notes'),
          pw.SizedBox(height: 7),
          for (final note in notes)
            pw.Container(
              width: double.infinity,
              margin: const pw.EdgeInsets.only(bottom: 7),
              padding: const pw.EdgeInsets.all(8),
              decoration: const pw.BoxDecoration(color: PdfColors.blueGrey50),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text('${note['title'] ?? 'Note'}',
                      style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
                  pw.SizedBox(height: 3),
                  pw.Text('${note['body'] ?? ''}'),
                  if ('${note['context'] ?? ''}'.trim().isNotEmpty)
                    pw.Text('Context: ${note['context']}',
                        style: const pw.TextStyle(
                            fontSize: 8, color: PdfColors.blueGrey600)),
                ],
              ),
            ),
        ],
        if (evidence.isNotEmpty) ...[
          pw.SizedBox(height: 18),
          _pdfSectionTitle('Photo evidence'),
          pw.SizedBox(height: 7),
          for (final evidenceRow in evidence.take(12))
            _pdfEvidence(evidenceRow),
        ],
      ],
    ),
  );

  final bytes = await document.save();
  final reportDirectory =
      Directory('${await getDatabasesPath()}/inspection_reports');
  await reportDirectory.create(recursive: true);
  await File('${reportDirectory.path}/$fileName')
      .writeAsBytes(bytes, flush: true);
  await Printing.sharePdf(bytes: bytes, filename: fileName);
}

pw.Widget _pdfMeta(String label, Object? value) => pw.SizedBox(
      width: 155,
      child: pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.start,
        children: [
          pw.Text(label.toUpperCase(),
              style: const pw.TextStyle(
                  fontSize: 7, color: PdfColors.blueGrey600)),
          pw.SizedBox(height: 2),
          pw.Text('${value ?? '-'}',
              style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold)),
        ],
      ),
    );

pw.Widget _pdfKpi(String label, String value, PdfColor color) => pw.Expanded(
      child: pw.Container(
        margin: const pw.EdgeInsets.only(right: 5),
        padding: const pw.EdgeInsets.all(7),
        decoration: pw.BoxDecoration(
          color: color.shade(0.1),
          borderRadius: pw.BorderRadius.circular(6),
        ),
        child: pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Text(value,
                style: pw.TextStyle(
                    fontSize: 14,
                    fontWeight: pw.FontWeight.bold,
                    color: color)),
            pw.Text(label,
                style: const pw.TextStyle(
                    fontSize: 7, color: PdfColors.blueGrey700)),
          ],
        ),
      ),
    );

pw.Widget _pdfSectionTitle(String title) => pw.Text(
      title,
      style: pw.TextStyle(
          fontSize: 14,
          fontWeight: pw.FontWeight.bold,
          color: PdfColors.blueGrey900),
    );

pw.Widget _responseTable(
  Map<String, dynamic> section,
  Map<String, Map<String, dynamic>> responseByQuestion,
) {
  final questions = section['questions'] as List? ?? const [];
  return pw.TableHelper.fromTextArray(
    headers: const ['Question', 'Result', 'Remarks', 'Platform'],
    data: questions.map((question) {
      final item = Map<String, dynamic>.from(question as Map);
      final response = responseByQuestion['${item['code']}'];
      return [
        '${item['text'] ?? '-'}',
        _responseLabel(response?['response_value']),
        '${response?['remarks'] ?? '-'}',
        '${response?['platform'] ?? '-'}',
      ];
    }).toList(),
    headerDecoration: const pw.BoxDecoration(color: PdfColors.blue800),
    headerStyle: pw.TextStyle(
        color: PdfColors.white, fontSize: 8, fontWeight: pw.FontWeight.bold),
    cellStyle: const pw.TextStyle(fontSize: 7.5),
    cellPadding: const pw.EdgeInsets.all(5),
    border: pw.TableBorder.all(color: PdfColors.blueGrey100, width: 0.5),
    oddRowDecoration: const pw.BoxDecoration(color: PdfColors.blueGrey50),
  );
}

pw.Widget _pdfEvidence(Map<String, dynamic> row) {
  final path = '${row['local_path'] ?? ''}';
  final file = File(path);
  if (!file.existsSync()) {
    return pw.Container(
      margin: const pw.EdgeInsets.only(bottom: 6),
      child:
          pw.Text('${row['caption'] ?? 'Photo'} (photo unavailable on device)'),
    );
  }
  try {
    return pw.Container(
      margin: const pw.EdgeInsets.only(bottom: 10),
      child: pw.Row(
        crossAxisAlignment: pw.CrossAxisAlignment.start,
        children: [
          pw.Container(
              width: 110,
              height: 78,
              child: pw.Image(pw.MemoryImage(file.readAsBytesSync()),
                  fit: pw.BoxFit.cover)),
          pw.SizedBox(width: 8),
          pw.Expanded(
              child: pw.Text(
                  '${row['caption'] ?? 'Inspection photo'}\n${row['context'] ?? ''}',
                  style: const pw.TextStyle(fontSize: 8))),
        ],
      ),
    );
  } catch (_) {
    return pw.Text('${row['caption'] ?? 'Photo'} (could not be embedded)');
  }
}

String _responseLabel(Object? value) {
  switch ('$value') {
    case 'pass':
      return 'PASS';
    case 'fail':
      return 'FAIL';
    case 'na':
      return 'N/A';
    default:
      return 'NOT ANSWERED';
  }
}

String _formatInspectionDate(Object? value) {
  final parsed = DateTime.tryParse('${value ?? ''}');
  return parsed == null
      ? '-'
      : DateFormat('dd MMM yyyy, HH:mm').format(parsed.toLocal());
}

String _safePdfFileName(String value) =>
    value.replaceAll(RegExp(r'[^A-Za-z0-9._-]+'), '-');

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

Future<void> exportReportPdf({
  required String title,
  required String subtitle,
  required List<Map<String, dynamic>> rows,
  required List<String> columns,
}) async {
  final document = pw.Document(title: title, author: 'Rail Inspect');
  final headers = columns.map(_reportColumnLabel).toList();
  document.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(26),
      header: (_) => pw.Row(
        mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
        children: [
          pw.Text('RAIL INSPECT',
              style: pw.TextStyle(
                  fontWeight: pw.FontWeight.bold, color: PdfColors.blue800)),
          pw.Text(DateFormat('dd MMM yyyy, HH:mm').format(DateTime.now()),
              style: const pw.TextStyle(fontSize: 8)),
        ],
      ),
      footer: (context) => pw.Align(
        alignment: pw.Alignment.centerRight,
        child: pw.Text('Page ${context.pageNumber} of ${context.pagesCount}',
            style: const pw.TextStyle(fontSize: 8)),
      ),
      build: (_) => [
        pw.SizedBox(height: 18),
        pw.Text(title,
            style: const pw.TextStyle(
                fontSize: 20, fontWeight: pw.FontWeight.bold)),
        pw.SizedBox(height: 4),
        pw.Text(subtitle,
            style:
                const pw.TextStyle(fontSize: 10, color: PdfColors.blueGrey700)),
        pw.SizedBox(height: 14),
        if (rows.isEmpty)
          pw.Text('No records match the selected filters.')
        else
          pw.TableHelper.fromTextArray(
            headers: headers,
            data: rows
                .map((row) =>
                    columns.map((column) => '${row[column] ?? '-'}').toList())
                .toList(),
            headerDecoration: const pw.BoxDecoration(color: PdfColors.blue800),
            headerStyle: const pw.TextStyle(
                fontSize: 8,
                color: PdfColors.white,
                fontWeight: pw.FontWeight.bold),
            cellStyle: const pw.TextStyle(fontSize: 7.5),
            cellPadding:
                const pw.EdgeInsets.symmetric(horizontal: 5, vertical: 5),
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
    filename: '${_safePdfFileName(title.toLowerCase())}.pdf',
  );
}

Future<File> exportReportCsv({
  required String title,
  required List<Map<String, dynamic>> rows,
  required List<String> columns,
}) async {
  final lines = <String>[
    columns.map(_csvCell).join(','),
    ...rows
        .map((row) => columns.map((column) => _csvCell(row[column])).join(',')),
  ];
  final directory = Directory(await getDatabasesPath());
  final file =
      File('${directory.path}/${_safePdfFileName(title.toLowerCase())}.csv');
  await file.writeAsString(lines.join('\n'));
  return file;
}

String _reportColumnLabel(String value) {
  const labels = {
    'sl_no': 'Sl.no',
    'project_id': 'PID',
    'date_of_sanction': 'Date of Sanction',
    'short_name_of_work': 'Name of work',
    'cost': 'Cost',
    'remarks': 'Remarks',
  };
  return labels[value] ??
      value
          .split('_')
          .map((part) => part.isEmpty
              ? part
              : '${part[0].toUpperCase()}${part.substring(1)}')
          .join(' ');
}

String _csvCell(Object? value) {
  final text = '${value ?? ''}'.replaceAll('"', '""').replaceAll('\n', ' ');
  return '"$text"';
}
