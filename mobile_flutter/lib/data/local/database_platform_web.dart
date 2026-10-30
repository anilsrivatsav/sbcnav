import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';

Future<String> configureDatabase() async {
  databaseFactory = databaseFactoryFfiWeb;
  return 'rail_inspect.db';
}
