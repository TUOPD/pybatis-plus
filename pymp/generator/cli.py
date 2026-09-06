# -*- coding: utf-8 -*-
"""
代码生成器 CLI 命令行入口
使用方式:
  python -m pymp.generator.cli --host localhost --db my_db --table instances --output ./out
"""
import argparse
import os
import pymysql
from pymp.generator.introspect import DbIntrospector
from pymp.generator.template import render_model_code, render_mapper_code


def main():
    parser = argparse.ArgumentParser(description="pymp 代码生成器 CLI")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", default="root", help="数据库密码")
    parser.add_argument("--db", required=True, help="数据库名称")
    parser.add_argument("--table", required=True, help="需要生成的表名")
    parser.add_argument("--output", default="./output", help="文件输出路径")

    args = parser.parse_args()

    # 1. 建立数据库连接
    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.db,
    )

    try:
        # 2. 逆向读取
        introspector = DbIntrospector(conn)
        info = introspector.get_table_info(args.db, args.table)

        # 3. 渲染代码
        model_code = render_model_code(info)
        mapper_code = render_mapper_code(info)

        # 4. 写入文件
        os.makedirs(args.output, exist_ok=True)

        model_file = os.path.join(args.output, f"{args.table}.py")
        mapper_file = os.path.join(args.output, f"{args.table}_mapper.py")

        with open(model_file, "w", encoding="utf-8") as f:
            f.write(model_code)

        with open(mapper_file, "w", encoding="utf-8") as f:
            f.write(mapper_code)

        print(f"🎉 代码生成成功！")
        print(f"  └─ Model:  {model_file}")
        print(f"  └─ Mapper: {mapper_file}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()