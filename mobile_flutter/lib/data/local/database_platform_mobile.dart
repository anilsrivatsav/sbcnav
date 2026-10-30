import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

Future<String> configureDatabase() async =>
    join(await getDatabasesPath(), 'rail_inspect.db');
