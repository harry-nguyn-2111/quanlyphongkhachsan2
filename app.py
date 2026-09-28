import streamlit as st
import pandas as pd
from datetime import datetime, date
import mysql.connector
from mysql.connector import Error

# ============================================================
# CẤU HÌNH STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Hotel Manager",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# MYSQL AIVEN
# ============================================================
# Thông tin database Aiven người dùng cung cấp.
# Khuyến nghị khi deploy thật: chuyển các thông tin này sang
# st.secrets hoặc biến môi trường để không phải ghi password
# trực tiếp trong source code.

DB_CONFIG = {
    "database": "defaultdb",
    "host": "mysql-425beae-quantricongngheso.d.aivencloud.com",
    "port": 28430,
    "user": "avnadmin",
    "password": "AVNS_rh-nVNeJhxVV2BtOJfT",
    # Aiven hiển thị SSL mode = REQUIRED
    "ssl_disabled": False,
    "ssl_verify_cert": False,
    "ssl_verify_identity": False,
    "connection_timeout": 15,
}

# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_db_connection():
    """Kết nối trực tiếp tới MySQL Aiven."""
    try:
        conn = mysql.connector.connect(
            host="mysql-425beae-quantricongngheso.d.aivencloud.com",
            port=28430,
            user="avnadmin",
            password="AVNS_rh-nVNeJhxVV2BtOJfT",
            database="defaultdb",
            ssl_disabled=False,
            ssl_verify_cert=False,
            ssl_verify_identity=False,
            connection_timeout=20,
        )

        if conn.is_connected():
            return conn

        st.error("❌ Không thể kết nối đến MySQL Aiven.")
        st.stop()

    except Error as e:
        st.error(
            "❌ Không thể kết nối MySQL Aiven.\n\n"
            f"Host: `mysql-425beae-quantricongngheso.d.aivencloud.com`\n"
            f"Port: `28430`\n\n"
            f"Lỗi MySQL: `{e}`"
        )
        st.stop()

    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        if conn.is_connected():
            return conn

        raise ConnectionError("Không thể kết nối MySQL Aiven.")

    except Error as e:
        st.error(
            "❌ Không thể kết nối MySQL Aiven.\\n\\n"
            f"Host: `{host}`\\n"
            f"Port: `{port}`\\n\\n"
            f"Lỗi MySQL: `{e}`"
        )
        st.stop()


def execute_query(query, params=None, fetch=False, many=False):
    """
    Thực thi SQL an toàn bằng parameterized query.
    fetch=True: trả về danh sách dict.
    """
    conn = get_db_connection()
    cursor = None

    try:
        # reconnect nếu connection bị mất
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=2)

        cursor = conn.cursor(dictionary=True)

        if many:
            cursor.executemany(query, params or [])
        else:
            cursor.execute(query, params or ())

        if fetch:
            return cursor.fetchall()

        conn.commit()
        return cursor.rowcount

    except Error as e:
        conn.rollback()
        raise e

    finally:
        if cursor is not None:
            cursor.close()


def execute_scalar(query, params=None):
    """Lấy một giá trị duy nhất từ database."""
    rows = execute_query(query, params, fetch=True)

    if not rows:
        return 0

    first_row = rows[0]
    return next(iter(first_row.values()))


def init_database():
    """Tạo toàn bộ bảng cần thiết."""
    queries = [
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_number VARCHAR(50) NOT NULL UNIQUE,
            room_type VARCHAR(50) NOT NULL,
            floor INT NOT NULL DEFAULT 1,
            price DECIMAL(15,2) NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'Trống',
            guest_name VARCHAR(255) NOT NULL DEFAULT '',
            phone VARCHAR(50) NOT NULL DEFAULT '',
            checkin DATE NULL,
            checkout DATE NULL,
            note TEXT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        """
        CREATE TABLE IF NOT EXISTS housekeeping (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_number VARCHAR(50) NOT NULL,
            task VARCHAR(255) NOT NULL,
            completed TINYINT(1) NOT NULL DEFAULT 0,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_housekeeping_room (room_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        """
        CREATE TABLE IF NOT EXISTS minibar (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_number VARCHAR(50) NOT NULL,
            item VARCHAR(255) NOT NULL,
            quantity INT NOT NULL DEFAULT 0,
            price DECIMAL(15,2) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_minibar_room (room_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_number VARCHAR(50) NOT NULL,
            guest_name VARCHAR(255) NOT NULL DEFAULT '',
            transaction_type VARCHAR(100) NOT NULL,
            amount DECIMAL(15,2) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_transactions_room (room_number),
            INDEX idx_transactions_type (transaction_type),
            INDEX idx_transactions_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]

    for query in queries:
        execute_query(query)


# ============================================================
# DỮ LIỆU MẶC ĐỊNH
# ============================================================

DEFAULT_ROOMS = [
    ("101", "Standard", 1, 500000),
    ("102", "Standard", 1, 500000),
    ("103", "Standard", 1, 500000),
    ("104", "Deluxe", 1, 700000),
    ("105", "Deluxe", 1, 700000),
    ("201", "Standard", 2, 500000),
    ("202", "Standard", 2, 500000),
    ("203", "Deluxe", 2, 700000),
    ("204", "Deluxe", 2, 700000),
    ("205", "Suite", 2, 1200000),
]


def seed_default_rooms():
    """Thêm phòng mẫu nếu database chưa có phòng."""
    count = execute_scalar("SELECT COUNT(*) AS total FROM rooms")

    if int(count or 0) == 0:
        query = """
            INSERT INTO rooms
            (room_number, room_type, floor, price, status)
            VALUES (%s, %s, %s, %s, 'Trống')
        """
        execute_query(query, DEFAULT_ROOMS, many=True)


# Khởi tạo DB ngay khi app chạy
try:
    init_database()
    seed_default_rooms()
except Error as e:
    st.error(f"❌ Lỗi khởi tạo database: {e}")
    st.stop()


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def money(value):
    try:
        return f"{float(value):,.0f} VNĐ"
    except (TypeError, ValueError):
        return "0 VNĐ"


def get_rooms():
    rows = execute_query(
        """
        SELECT
            id,
            room_number,
            room_type,
            floor,
            price,
            status,
            guest_name,
            phone,
            DATE_FORMAT(checkin, '%%Y-%%m-%%d') AS checkin,
            DATE_FORMAT(checkout, '%%Y-%%m-%%d') AS checkout,
            note,
            created_at,
            updated_at
        FROM rooms
        ORDER BY room_number
        """,
        fetch=True
    )
    return pd.DataFrame(rows)


def update_room_status(room_number, status):
    execute_query(
        """
        UPDATE rooms
        SET status=%s
        WHERE room_number=%s
        """,
        (status, room_number)
    )


def add_transaction(room_number, guest_name, transaction_type, amount):
    execute_query(
        """
        INSERT INTO transactions
        (room_number, guest_name, transaction_type, amount, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (
            room_number,
            guest_name,
            transaction_type,
            float(amount)
        )
    )


def get_minibar_total(room_number):
    value = execute_scalar(
        """
        SELECT COALESCE(SUM(quantity * price), 0) AS total
        FROM minibar
        WHERE room_number=%s
        """,
        (room_number,)
    )
    return float(value or 0)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏨 HOTEL MANAGER")
st.sidebar.caption("Hệ thống quản lý khách sạn • MySQL Aiven")

menu = st.sidebar.radio(
    "MENU",
    [
        "📊 Tổng quan",
        "🛏️ Quản lý phòng",
        "📋 Nhận phòng",
        "🚪 Trả phòng",
        "🧹 Buồng phòng",
        "🍾 Minibar",
        "💰 Doanh thu",
        "⚙️ Cài đặt"
    ]
)

st.sidebar.divider()

rooms = get_rooms()

total_rooms = len(rooms)
occupied = len(rooms[rooms["status"] == "Đang ở"])
available = len(rooms[rooms["status"] == "Trống"])
cleaning = len(rooms[rooms["status"] == "Đang dọn"])
maintenance = len(rooms[rooms["status"] == "Bảo trì"])

st.sidebar.metric("Tổng số phòng", total_rooms)
st.sidebar.metric("Đang có khách", occupied)


# ============================================================
# 1. TỔNG QUAN
# ============================================================

if menu == "📊 Tổng quan":

    st.title("📊 Tổng quan khách sạn")
    st.caption(
        f"Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("🏨 Tổng phòng", total_rooms)
    col2.metric("🟢 Phòng trống", available)
    col3.metric("🔴 Đang ở", occupied)
    col4.metric("🧹 Đang dọn", cleaning)
    col5.metric("🔧 Bảo trì", maintenance)

    st.divider()

    occupancy = 0
    if total_rooms > 0:
        occupancy = occupied / total_rooms * 100

    st.subheader("📈 Công suất phòng")
    st.progress(int(occupancy))
    st.write(f"**{occupancy:.1f}%** phòng đang có khách")

    st.divider()

    st.subheader("🛏️ Tình trạng phòng")

    cols = st.columns(5)

    status_icons = {
        "Trống": "🟢",
        "Đang ở": "🔴",
        "Đang dọn": "🟡",
        "Bảo trì": "⚫"
    }

    for index, room in rooms.iterrows():

        col = cols[index % 5]

        with col:
            st.markdown(
                f"""
### {room['room_number']}
{status_icons.get(room['status'], "⚪")} **{room['status']}**

Loại: {room['room_type']}  
Giá: {money(room['price'])}
"""
            )


# ============================================================
# 2. QUẢN LÝ PHÒNG
# ============================================================

elif menu == "🛏️ Quản lý phòng":

    st.title("🛏️ Quản lý phòng")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Chưa có phòng.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            filter_status = st.selectbox(
                "Lọc theo trạng thái",
                ["Tất cả", "Trống", "Đang ở", "Đang dọn", "Bảo trì"]
            )

        with col2:
            search = st.text_input("🔎 Tìm số phòng")

        filtered = rooms.copy()

        if filter_status != "Tất cả":
            filtered = filtered[
                filtered["status"] == filter_status
            ]

        if search:
            filtered = filtered[
                filtered["room_number"].astype(str).str.contains(
                    search,
                    case=False,
                    na=False
                )
            ]

        st.dataframe(
            filtered[
                [
                    "room_number",
                    "room_type",
                    "floor",
                    "price",
                    "status",
                    "guest_name",
                    "phone",
                    "checkin",
                    "checkout"
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "room_number": "Phòng",
                "room_type": "Loại phòng",
                "floor": "Tầng",
                "price": st.column_config.NumberColumn(
                    "Giá phòng",
                    format="%.0f VNĐ"
                ),
                "status": "Trạng thái",
                "guest_name": "Khách",
                "phone": "SĐT",
                "checkin": "Check-in",
                "checkout": "Check-out"
            }
        )

        st.divider()

        st.subheader("🔄 Thay đổi trạng thái phòng")

        room_number = st.selectbox(
            "Chọn phòng",
            rooms["room_number"].tolist()
        )

        new_status = st.selectbox(
            "Trạng thái mới",
            [
                "Trống",
                "Đang ở",
                "Đang dọn",
                "Bảo trì"
            ]
        )

        if st.button(
            "💾 Cập nhật trạng thái",
            type="primary"
        ):
            try:
                update_room_status(room_number, new_status)
                st.success(
                    f"Phòng {room_number} → {new_status}"
                )
                st.rerun()
            except Error as e:
                st.error(f"Lỗi cập nhật: {e}")


# ============================================================
# 3. NHẬN PHÒNG
# ============================================================

elif menu == "📋 Nhận phòng":

    st.title("📋 Nhận phòng")

    available_rooms = rooms[
        rooms["status"] == "Trống"
    ]

    if available_rooms.empty:

        st.warning("Hiện không có phòng trống.")

    else:

        with st.form("checkin_form"):

            col1, col2 = st.columns(2)

            with col1:

                room_number = st.selectbox(
                    "🛏️ Phòng",
                    available_rooms["room_number"].tolist()
                )

                guest_name = st.text_input(
                    "👤 Tên khách *"
                )

                phone = st.text_input(
                    "📱 Số điện thoại"
                )

            with col2:

                checkin_date = st.date_input(
                    "📅 Ngày nhận phòng",
                    date.today()
                )

                checkout_date = st.date_input(
                    "📅 Ngày trả phòng",
                    date.today()
                )

                note = st.text_area(
                    "📝 Ghi chú"
                )

            submit = st.form_submit_button(
                "✅ Xác nhận nhận phòng",
                type="primary"
            )

        if submit:

            if not guest_name.strip():

                st.error("Vui lòng nhập tên khách.")

            elif checkout_date < checkin_date:

                st.error(
                    "Ngày trả phòng không được trước ngày nhận phòng."
                )

            else:

                try:
                    execute_query(
                        """
                        UPDATE rooms
                        SET
                            status='Đang ở',
                            guest_name=%s,
                            phone=%s,
                            checkin=%s,
                            checkout=%s,
                            note=%s
                        WHERE room_number=%s
                        """,
                        (
                            guest_name.strip(),
                            phone.strip(),
                            checkin_date,
                            checkout_date,
                            note.strip(),
                            room_number
                        )
                    )

                    room_data = rooms[
                        rooms["room_number"] == room_number
                    ].iloc[0]

                    # Ghi nhận tiền phòng vào giao dịch.
                    # Giữ nguyên cách hoạt động của phiên bản SQLite.
                    add_transaction(
                        room_number,
                        guest_name.strip(),
                        "Tiền phòng",
                        room_data["price"]
                    )

                    st.success(
                        f"✅ Đã nhận phòng {room_number} cho {guest_name}"
                    )

                    st.rerun()

                except Error as e:
                    st.error(f"❌ Lỗi nhận phòng: {e}")


# ============================================================
# 4. TRẢ PHÒNG
# ============================================================

elif menu == "🚪 Trả phòng":

    st.title("🚪 Trả phòng")

    occupied_rooms = rooms[
        rooms["status"] == "Đang ở"
    ]

    if occupied_rooms.empty:

        st.info("Hiện không có khách đang ở.")

    else:

        room_number = st.selectbox(
            "Chọn phòng trả",
            occupied_rooms["room_number"].tolist()
        )

        room = occupied_rooms[
            occupied_rooms["room_number"] == room_number
        ].iloc[0]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Phòng",
            room["room_number"]
        )

        col2.metric(
            "Khách",
            room["guest_name"]
        )

        col3.metric(
            "Giá phòng",
            money(room["price"])
        )

        st.divider()

        minibar_total = get_minibar_total(room_number)

        other_charge = st.number_input(
            "💳 Chi phí phát sinh khác",
            min_value=0.0,
            step=50000.0
        )

        room_price = float(room["price"])
        total = room_price + minibar_total + other_charge

        st.subheader("💰 Tổng thanh toán")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Tiền phòng",
            money(room_price)
        )

        c2.metric(
            "Minibar",
            money(minibar_total)
        )

        c3.metric(
            "Phát sinh",
            money(other_charge)
        )

        c4.metric(
            "TỔNG",
            money(total)
        )

        if st.button(
            "🚪 Xác nhận trả phòng",
            type="primary"
        ):

            try:
                # Ghi giao dịch thanh toán.
                add_transaction(
                    room_number,
                    room["guest_name"],
                    "Thanh toán",
                    total
                )

                # Nếu có chi phí phát sinh, ghi riêng để dễ thống kê.
                if other_charge > 0:
                    add_transaction(
                        room_number,
                        room["guest_name"],
                        "Chi phí phát sinh",
                        other_charge
                    )

                execute_query(
                    """
                    UPDATE rooms
                    SET
                        status='Đang dọn',
                        guest_name='',
                        phone='',
                        checkin=NULL,
                        checkout=NULL,
                        note=''
                    WHERE room_number=%s
                    """,
                    (room_number,)
                )

                execute_query(
                    """
                    DELETE FROM minibar
                    WHERE room_number=%s
                    """,
                    (room_number,)
                )

                st.success(
                    f"Đã trả phòng {room_number}. "
                    f"Tổng thanh toán: {money(total)}"
                )

                st.rerun()

            except Error as e:
                st.error(f"❌ Lỗi trả phòng: {e}")


# ============================================================
# 5. BUỒNG PHÒNG
# ============================================================

elif menu == "🧹 Buồng phòng":

    st.title("🧹 Quản lý buồng phòng")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Chưa có phòng.")
    else:
        room_number = st.selectbox(
            "Chọn phòng",
            rooms["room_number"].tolist()
        )

        st.divider()

        tasks = [
            "Dọn phòng",
            "Thay ga giường",
            "Thay khăn",
            "Dọn nhà vệ sinh",
            "Hút bụi",
            "Lau sàn",
            "Kiểm tra minibar",
            "Kiểm tra TV",
            "Kiểm tra điều hòa",
            "Kiểm tra đèn",
            "Bổ sung nước uống",
            "Bổ sung đồ vệ sinh",
            "Kiểm tra tài sản trong phòng"
        ]

        st.subheader(
            f"📋 Checklist phòng {room_number}"
        )

        completed_tasks = []

        for index, task in enumerate(tasks):

            checked = st.checkbox(
                task,
                key=f"housekeeping_{room_number}_{index}"
            )

            if checked:
                completed_tasks.append(task)

        progress = len(completed_tasks) / len(tasks)

        st.progress(progress)

        st.write(
            f"Hoàn thành **{len(completed_tasks)}/{len(tasks)}** công việc"
        )

        if st.button(
            "✅ Hoàn thành vệ sinh",
            type="primary"
        ):

            if len(completed_tasks) < len(tasks):

                st.warning(
                    "Bạn chưa hoàn thành toàn bộ checklist."
                )

            else:

                try:
                    # Xóa checklist cũ của phòng.
                    execute_query(
                        """
                        DELETE FROM housekeeping
                        WHERE room_number=%s
                        """,
                        (room_number,)
                    )

                    # Lưu checklist đã hoàn thành.
                    rows = [
                        (
                            room_number,
                            task,
                            1
                        )
                        for task in tasks
                    ]

                    execute_query(
                        """
                        INSERT INTO housekeeping
                        (room_number, task, completed, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        """,
                        rows,
                        many=True
                    )

                    update_room_status(
                        room_number,
                        "Trống"
                    )

                    st.success(
                        f"Phòng {room_number} đã sẵn sàng bán."
                    )

                    st.rerun()

                except Error as e:
                    st.error(f"❌ Lỗi lưu checklist: {e}")


# ============================================================
# 6. MINIBAR
# ============================================================

elif menu == "🍾 Minibar":

    st.title("🍾 Quản lý Minibar")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Chưa có phòng.")
    else:

        room_number = st.selectbox(
            "Chọn phòng",
            rooms["room_number"].tolist()
        )

        minibar_items = [
            ("Nước suối", 15000),
            ("Coca Cola", 20000),
            ("Pepsi", 20000),
            ("Bia", 30000),
            ("Snack", 25000),
            ("Chocolate", 35000),
            ("Cà phê", 25000)
        ]

        item_names = [
            item[0]
            for item in minibar_items
        ]

        item = st.selectbox(
            "Sản phẩm",
            item_names
        )

        item_price = dict(minibar_items)[item]

        quantity = st.number_input(
            "Số lượng",
            min_value=1,
            value=1,
            step=1
        )

        st.write(
            f"Đơn giá: **{money(item_price)}**"
        )

        if st.button(
            "➕ Thêm Minibar",
            type="primary"
        ):

            try:
                execute_query(
                    """
                    INSERT INTO minibar
                    (room_number, item, quantity, price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        room_number,
                        item,
                        int(quantity),
                        item_price
                    )
                )

                st.success(
                    f"Đã thêm {quantity} x {item}"
                )

                st.rerun()

            except Error as e:
                st.error(f"❌ Lỗi thêm minibar: {e}")

        st.divider()

        minibar_rows = execute_query(
            """
            SELECT
                id,
                room_number,
                item,
                quantity,
                price,
                quantity * price AS total
            FROM minibar
            WHERE room_number=%s
            ORDER BY id DESC
            """,
            (room_number,),
            fetch=True
        )

        minibar_data = pd.DataFrame(minibar_rows)

        if not minibar_data.empty:

            st.dataframe(
                minibar_data[
                    [
                        "item",
                        "quantity",
                        "price",
                        "total"
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "item": "Sản phẩm",
                    "quantity": "SL",
                    "price": st.column_config.NumberColumn(
                        "Đơn giá",
                        format="%.0f VNĐ"
                    ),
                    "total": st.column_config.NumberColumn(
                        "Thành tiền",
                        format="%.0f VNĐ"
                    )
                }
            )

            total = minibar_data["total"].sum()

            st.metric(
                "Tổng Minibar",
                money(total)
            )

        else:

            st.info(
                "Phòng này chưa có sản phẩm minibar."
            )


# ============================================================
# 7. DOANH THU
# ============================================================

elif menu == "💰 Doanh thu":

    st.title("💰 Doanh thu")

    transactions_rows = execute_query(
        """
        SELECT
            id,
            room_number,
            guest_name,
            transaction_type,
            amount,
            DATE_FORMAT(created_at, '%%d/%%m/%%Y %%H:%%i:%%s') AS created_at
        FROM transactions
        ORDER BY id DESC
        """,
        fetch=True
    )

    transactions = pd.DataFrame(transactions_rows)

    if transactions.empty:

        st.info("Chưa có giao dịch.")

    else:

        total_revenue = transactions["amount"].sum()

        room_revenue = transactions[
            transactions["transaction_type"] == "Tiền phòng"
        ]["amount"].sum()

        payment_revenue = transactions[
            transactions["transaction_type"] == "Thanh toán"
        ]["amount"].sum()

        extra_revenue = transactions[
            transactions["transaction_type"] == "Chi phí phát sinh"
        ]["amount"].sum()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "💰 Tổng giao dịch",
            money(total_revenue)
        )

        c2.metric(
            "🛏️ Tiền phòng",
            money(room_revenue)
        )

        c3.metric(
            "💳 Thanh toán",
            money(payment_revenue)
        )

        c4.metric(
            "➕ Phát sinh",
            money(extra_revenue)
        )

        st.divider()

        st.subheader("📋 Lịch sử giao dịch")

        st.dataframe(
            transactions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "room_number": "Phòng",
                "guest_name": "Khách",
                "transaction_type": "Loại giao dịch",
                "amount": st.column_config.NumberColumn(
                    "Số tiền",
                    format="%.0f VNĐ"
                ),
                "created_at": "Thời gian"
            }
        )

        st.subheader("📊 Doanh thu theo loại")

        revenue_chart = transactions.groupby(
            "transaction_type"
        )["amount"].sum()

        st.bar_chart(revenue_chart)


# ============================================================
# 8. CÀI ĐẶT
# ============================================================

elif menu == "⚙️ Cài đặt":

    st.title("⚙️ Cài đặt hệ thống")

    st.subheader("➕ Thêm phòng mới")

    with st.form("add_room"):

        room_number = st.text_input(
            "Số phòng"
        )

        room_type = st.selectbox(
            "Loại phòng",
            [
                "Standard",
                "Deluxe",
                "Suite",
                "Family",
                "VIP"
            ]
        )

        floor = st.number_input(
            "Tầng",
            min_value=1,
            value=1,
            step=1
        )

        price = st.number_input(
            "Giá phòng",
            min_value=0.0,
            value=500000.0,
            step=50000.0
        )

        submit = st.form_submit_button(
            "➕ Thêm phòng"
        )

    if submit:

        if not room_number.strip():

            st.error("Vui lòng nhập số phòng.")

        else:

            try:

                execute_query(
                    """
                    INSERT INTO rooms
                    (room_number, room_type, floor, price, status)
                    VALUES (%s, %s, %s, %s, 'Trống')
                    """,
                    (
                        room_number.strip(),
                        room_type,
                        int(floor),
                        float(price)
                    )
                )

                st.success(
                    f"Đã thêm phòng {room_number}"
                )

                st.rerun()

            except Error as e:

                if getattr(e, "errno", None) == 1062:
                    st.error(
                        "Số phòng này đã tồn tại."
                    )
                else:
                    st.error(
                        f"❌ Không thể thêm phòng: {e}"
                    )

    st.divider()

    st.subheader("🗑️ Xóa phòng")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Không có phòng để xóa.")
    else:

        delete_room = st.selectbox(
            "Chọn phòng muốn xóa",
            rooms["room_number"].tolist()
        )

        if st.button(
            "🗑️ Xóa phòng",
            type="secondary"
        ):

            try:

                # Không cho xóa phòng đang có khách.
                current_room = rooms[
                    rooms["room_number"] == delete_room
                ].iloc[0]

                if current_room["status"] == "Đang ở":
                    st.error(
                        "Không thể xóa phòng đang có khách."
                    )
                else:

                    execute_query(
                        """
                        DELETE FROM minibar
                        WHERE room_number=%s
                        """,
                        (delete_room,)
                    )

                    execute_query(
                        """
                        DELETE FROM housekeeping
                        WHERE room_number=%s
                        """,
                        (delete_room,)
                    )

                    execute_query(
                        """
                        DELETE FROM rooms
                        WHERE room_number=%s
                        """,
                        (delete_room,)
                    )

                    st.success(
                        f"Đã xóa phòng {delete_room}"
                    )

                    st.rerun()

            except Error as e:
                st.error(f"❌ Lỗi xóa phòng: {e}")


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏨 Hotel Manager v2.0 • MySQL Aiven"
)

st.sidebar.caption(
    "Quản lý phòng • Khách • Buồng phòng • Minibar • Doanh thu"
)
