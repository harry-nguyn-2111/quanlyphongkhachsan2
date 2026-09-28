import os
from datetime import datetime, date

import mysql.connector
from mysql.connector import Error, IntegrityError
import pandas as pd
import streamlit as st


# ============================================================
# CẤU HÌNH STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Hotel Manager",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CẤU HÌNH MYSQL AIVEN
# ============================================================
# Host và Port lấy đúng từ Aiven:
# mysql-425beae-quantriconqngheso.d.aivencloud.com
# Port: 28430
#
# Bạn CHỈ cần thay MYSQL_PASSWORD bằng mật khẩu Aiven hiện tại.
# Không cần tạo file hotel.db nữa.

MYSQL_HOST = "mysql-425beae-quantriconqngheso.d.aivencloud.com"
MYSQL_PORT = 28430
MYSQL_USER = "avnadmin"
MYSQL_DATABASE = "defaultdb"

# Có thể đặt mật khẩu bằng biến môi trường MYSQL_PASSWORD.
# Nếu chưa có biến môi trường thì nhập mật khẩu vào dòng bên dưới.
MYSQL_PASSWORD = "AVNS_rh-nVNeJhxVV2BtOJfT"


# ============================================================
# KẾT NỐI MYSQL
# ============================================================

@st.cache_resource
def get_connection():
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,

            # Aiven yêu cầu kết nối TLS/SSL.
            # ssl_verify_cert=False tương ứng với kiểu REQUIRED:
            # có mã hóa TLS nhưng không bắt buộc xác minh CA.
            ssl_disabled=False,
            ssl_verify_cert=False,
            ssl_verify_identity=False,

            connection_timeout=30,
            autocommit=False,
        )

        if conn.is_connected():
            return conn

        return None

    except Error as e:
        st.error("❌ Không thể kết nối MySQL Aiven.")
        st.code(str(e))
        return None


conn = get_connection()

if conn is None:
    st.stop()


# ============================================================
# HÀM DATABASE
# ============================================================

def ensure_connection():
    """Kiểm tra và kết nối lại nếu connection bị mất."""
    global conn

    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=2)
    except Exception:
        st.cache_resource.clear()
        conn = get_connection()

    if conn is None:
        st.error("❌ Không thể kết nối lại MySQL.")
        st.stop()

    return conn


def execute(sql, params=None, fetch=False):
    """Thực thi SQL và tự đóng cursor."""
    ensure_connection()

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(sql, params or ())

        if fetch:
            rows = cursor.fetchall()
            columns = cursor.column_names
            return rows, columns

        conn.commit()
        return None

    except Error:
        conn.rollback()
        raise

    finally:
        cursor.close()


def query_df(sql, params=None):
    """Chạy SELECT và trả về pandas DataFrame."""
    rows, columns = execute(sql, params, fetch=True)
    return pd.DataFrame(rows, columns=columns)


def scalar(sql, params=None):
    """Lấy một giá trị duy nhất từ SELECT."""
    ensure_connection()

    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        cursor.close()


# ============================================================
# TẠO DATABASE TABLE
# ============================================================

def init_database():
    ensure_connection()

    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_number VARCHAR(20) NOT NULL UNIQUE,
                room_type VARCHAR(50) NOT NULL,
                floor INT NOT NULL,
                price DECIMAL(15,2) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'Trống',
                guest_name VARCHAR(255) DEFAULT '',
                phone VARCHAR(50) DEFAULT '',
                checkin DATE NULL,
                checkout DATE NULL,
                note TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS housekeeping (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_number VARCHAR(20) NOT NULL,
                task VARCHAR(255) NOT NULL,
                completed TINYINT(1) DEFAULT 0,
                updated_at DATETIME
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minibar (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_number VARCHAR(20) NOT NULL,
                item VARCHAR(255) NOT NULL,
                quantity INT NOT NULL DEFAULT 0,
                price DECIMAL(15,2) NOT NULL DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_number VARCHAR(20) NOT NULL,
                guest_name VARCHAR(255) DEFAULT '',
                transaction_type VARCHAR(100) NOT NULL,
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()

    except Error:
        conn.rollback()
        raise

    finally:
        cursor.close()


try:
    init_database()
except Error as e:
    st.error("❌ Không thể tạo bảng trong MySQL Aiven.")
    st.code(str(e))
    st.stop()


# ============================================================
# DỮ LIỆU PHÒNG MẶC ĐỊNH
# ============================================================

default_rooms = [
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


def insert_default_rooms():
    ensure_connection()

    cursor = conn.cursor()

    try:
        for room in default_rooms:
            cursor.execute("""
                INSERT IGNORE INTO rooms
                (room_number, room_type, floor, price)
                VALUES (%s, %s, %s, %s)
            """, room)

        conn.commit()

    except Error:
        conn.rollback()
        raise

    finally:
        cursor.close()


try:
    insert_default_rooms()
except Error as e:
    st.error("❌ Không thể thêm dữ liệu phòng mặc định.")
    st.code(str(e))
    st.stop()


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def money(value):
    if value is None:
        value = 0

    try:
        return f"{float(value):,.0f} VNĐ"
    except (TypeError, ValueError):
        return "0 VNĐ"


def get_rooms():
    return query_df("""
        SELECT
            id,
            room_number,
            room_type,
            floor,
            price,
            status,
            COALESCE(guest_name, '') AS guest_name,
            COALESCE(phone, '') AS phone,
            checkin,
            checkout,
            COALESCE(note, '') AS note
        FROM rooms
        ORDER BY CAST(room_number AS UNSIGNED), room_number
    """)


def update_room_status(room_number, status):
    execute(
        """
        UPDATE rooms
        SET status=%s
        WHERE room_number=%s
        """,
        (status, room_number),
    )


def add_transaction(
    room_number,
    guest_name,
    transaction_type,
    amount,
):
    execute(
        """
        INSERT INTO transactions
        (room_number, guest_name, transaction_type, amount, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            room_number,
            guest_name,
            transaction_type,
            amount,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏨 HOTEL MANAGER")
st.sidebar.caption("Hệ thống quản lý khách sạn")

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
        "⚙️ Cài đặt",
    ],
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

    st.write(
        f"**{occupancy:.1f}%** phòng đang có khách"
    )

    st.divider()

    st.subheader("🛏️ Tình trạng phòng")

    cols = st.columns(5)

    status_colors = {
        "Trống": "🟢",
        "Đang ở": "🔴",
        "Đang dọn": "🟡",
        "Bảo trì": "⚫",
    }

    for index, room in rooms.iterrows():

        col = cols[index % 5]

        with col:
            st.markdown(
                f"""
                ### {room['room_number']}
                {status_colors.get(room['status'], '⚪')} **{room['status']}**

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
        st.warning("Chưa có phòng.")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        filter_status = st.selectbox(
            "Lọc theo trạng thái",
            [
                "Tất cả",
                "Trống",
                "Đang ở",
                "Đang dọn",
                "Bảo trì",
            ],
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
                na=False,
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
                "checkout",
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
                format="%d VNĐ",
            ),
            "status": "Trạng thái",
            "guest_name": "Khách",
            "phone": "SĐT",
            "checkin": "Check-in",
            "checkout": "Check-out",
        },
    )

    st.divider()

    st.subheader("🔄 Thay đổi trạng thái phòng")

    room_number = st.selectbox(
        "Chọn phòng",
        rooms["room_number"].tolist(),
    )

    new_status = st.selectbox(
        "Trạng thái mới",
        [
            "Trống",
            "Đang ở",
            "Đang dọn",
            "Bảo trì",
        ],
    )

    if st.button(
        "💾 Cập nhật trạng thái",
        type="primary",
    ):
        update_room_status(
            room_number,
            new_status,
        )

        st.success(
            f"Phòng {room_number} → {new_status}"
        )

        st.rerun()


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
                    available_rooms["room_number"].tolist(),
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
                    date.today(),
                )

                checkout_date = st.date_input(
                    "📅 Ngày trả phòng",
                    date.today(),
                )

                note = st.text_area(
                    "📝 Ghi chú"
                )

            submit = st.form_submit_button(
                "✅ Xác nhận nhận phòng",
                type="primary",
            )

        if submit:

            if not guest_name.strip():

                st.error("Vui lòng nhập tên khách.")

            elif checkout_date < checkin_date:

                st.error(
                    "Ngày trả phòng không được trước ngày nhận phòng."
                )

            else:

                room_data = rooms[
                    rooms["room_number"] == room_number
                ].iloc[0]

                try:
                    execute(
                        """
                        UPDATE rooms
                        SET status='Đang ở',
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
                            room_number,
                        ),
                    )

                    add_transaction(
                        room_number,
                        guest_name.strip(),
                        "Tiền phòng",
                        float(room_data["price"]),
                    )

                    st.success(
                        f"✅ Đã nhận phòng {room_number} "
                        f"cho {guest_name.strip()}"
                    )

                    st.rerun()

                except Error as e:
                    st.error("❌ Không thể nhận phòng.")
                    st.code(str(e))


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
            occupied_rooms["room_number"].tolist(),
        )

        room = occupied_rooms[
            occupied_rooms["room_number"] == room_number
        ].iloc[0]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Phòng",
            room["room_number"],
        )

        col2.metric(
            "Khách",
            room["guest_name"],
        )

        col3.metric(
            "Giá phòng",
            money(room["price"]),
        )

        st.divider()

        minibar_total = scalar(
            """
            SELECT COALESCE(SUM(quantity * price), 0)
            FROM minibar
            WHERE room_number=%s
            """,
            (room_number,),
        )

        other_charge = st.number_input(
            "💳 Chi phí phát sinh khác",
            min_value=0,
            step=50000,
        )

        room_price = float(room["price"])
        minibar_total = float(minibar_total or 0)
        other_charge = float(other_charge)

        total = (
            room_price
            + minibar_total
            + other_charge
        )

        st.subheader("💰 Tổng thanh toán")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Tiền phòng",
            money(room_price),
        )

        c2.metric(
            "Minibar",
            money(minibar_total),
        )

        c3.metric(
            "Phát sinh",
            money(other_charge),
        )

        c4.metric(
            "TỔNG",
            money(total),
        )

        if st.button(
            "🚪 Xác nhận trả phòng",
            type="primary",
        ):

            try:

                # Ghi giao dịch thanh toán
                add_transaction(
                    room_number,
                    room["guest_name"],
                    "Thanh toán",
                    total,
                )

                # Chuyển phòng sang trạng thái đang dọn
                execute(
                    """
                    UPDATE rooms
                    SET status='Đang dọn',
                        guest_name='',
                        phone='',
                        checkin=NULL,
                        checkout=NULL,
                        note=''
                    WHERE room_number=%s
                    """,
                    (room_number,),
                )

                # Xóa minibar của lượt khách cũ
                execute(
                    """
                    DELETE FROM minibar
                    WHERE room_number=%s
                    """,
                    (room_number,),
                )

                st.success(
                    f"Đã trả phòng {room_number}. "
                    f"Tổng thanh toán: {money(total)}"
                )

                st.rerun()

            except Error as e:
                st.error("❌ Không thể trả phòng.")
                st.code(str(e))


# ============================================================
# 5. BUỒNG PHÒNG
# ============================================================

elif menu == "🧹 Buồng phòng":

    st.title("🧹 Quản lý buồng phòng")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Chưa có phòng.")
        st.stop()

    room_number = st.selectbox(
        "Chọn phòng",
        rooms["room_number"].tolist(),
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
        "Kiểm tra tài sản trong phòng",
    ]

    st.subheader(
        f"📋 Checklist phòng {room_number}"
    )

    completed_tasks = []

    for task in tasks:

        checked = st.checkbox(
            task,
            key=f"{room_number}_{task}",
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
        type="primary",
    ):

        if len(completed_tasks) < len(tasks):

            st.warning(
                "Bạn chưa hoàn thành toàn bộ checklist."
            )

        else:

            try:

                update_room_status(
                    room_number,
                    "Trống",
                )

                # Lưu checklist vào MySQL
                for task in tasks:
                    execute(
                        """
                        INSERT INTO housekeeping
                        (room_number, task, completed, updated_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            room_number,
                            task,
                            1,
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        ),
                    )

                st.success(
                    f"Phòng {room_number} đã sẵn sàng bán."
                )

                st.rerun()

            except Error as e:
                st.error("❌ Không thể lưu checklist.")
                st.code(str(e))


# ============================================================
# 6. MINIBAR
# ============================================================

elif menu == "🍾 Minibar":

    st.title("🍾 Quản lý Minibar")

    rooms = get_rooms()

    if rooms.empty:
        st.info("Chưa có phòng.")
        st.stop()

    room_number = st.selectbox(
        "Chọn phòng",
        rooms["room_number"].tolist(),
    )

    minibar_items = [
        ("Nước suối", 15000),
        ("Coca Cola", 20000),
        ("Pepsi", 20000),
        ("Bia", 30000),
        ("Snack", 25000),
        ("Chocolate", 35000),
        ("Cà phê", 25000),
    ]

    item_names = [
        item[0]
        for item in minibar_items
    ]

    item = st.selectbox(
        "Sản phẩm",
        item_names,
    )

    item_price = dict(minibar_items)[item]

    quantity = st.number_input(
        "Số lượng",
        min_value=1,
        value=1,
        step=1,
    )

    st.write(
        f"Đơn giá: **{money(item_price)}**"
    )

    if st.button(
        "➕ Thêm Minibar",
        type="primary",
    ):

        try:

            execute(
                """
                INSERT INTO minibar
                (room_number, item, quantity, price)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    room_number,
                    item,
                    quantity,
                    item_price,
                ),
            )

            st.success(
                f"Đã thêm {quantity} x {item}"
            )

            st.rerun()

        except Error as e:
            st.error("❌ Không thể thêm minibar.")
            st.code(str(e))

    st.divider()

    minibar_data = query_df(
        """
        SELECT
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
    )

    if not minibar_data.empty:

        st.dataframe(
            minibar_data,
            use_container_width=True,
            hide_index=True,
        )

        total = minibar_data["total"].sum()

        st.metric(
            "Tổng Minibar",
            money(total),
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

    transactions = query_df(
        """
        SELECT
            id,
            room_number,
            guest_name,
            transaction_type,
            amount,
            created_at
        FROM transactions
        ORDER BY id DESC
        """
    )

    if transactions.empty:

        st.info("Chưa có giao dịch.")

    else:

        transactions["amount"] = pd.to_numeric(
            transactions["amount"],
            errors="coerce",
        ).fillna(0)

        total_revenue = transactions["amount"].sum()

        room_revenue = transactions[
            transactions["transaction_type"] == "Tiền phòng"
        ]["amount"].sum()

        payment_revenue = transactions[
            transactions["transaction_type"] == "Thanh toán"
        ]["amount"].sum()

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "💰 Tổng doanh thu",
            money(total_revenue),
        )

        c2.metric(
            "🛏️ Tiền phòng",
            money(room_revenue),
        )

        c3.metric(
            "💳 Thanh toán",
            money(payment_revenue),
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
                    format="%d VNĐ",
                ),
                "created_at": "Thời gian",
            },
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
                "VIP",
            ],
        )

        floor = st.number_input(
            "Tầng",
            min_value=1,
            value=1,
        )

        price = st.number_input(
            "Giá phòng",
            min_value=0,
            value=500000,
            step=50000,
        )

        submit = st.form_submit_button(
            "➕ Thêm phòng"
        )

    if submit:

        room_number = room_number.strip()

        if not room_number:

            st.error("Vui lòng nhập số phòng.")

        elif price < 0:

            st.error("Giá phòng không hợp lệ.")

        else:

            try:

                execute(
                    """
                    INSERT INTO rooms
                    (room_number, room_type, floor, price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        room_number,
                        room_type,
                        floor,
                        price,
                    ),
                )

                st.success(
                    f"Đã thêm phòng {room_number}"
                )

                st.rerun()

            except IntegrityError:

                st.error(
                    "Số phòng này đã tồn tại."
                )

            except Error as e:

                st.error(
                    "❌ Không thể thêm phòng."
                )
                st.code(str(e))

    st.divider()

    st.subheader("🗑️ Xóa phòng")

    rooms = get_rooms()

    if rooms.empty:

        st.info("Không có phòng để xóa.")

    else:

        delete_room = st.selectbox(
            "Chọn phòng muốn xóa",
            rooms["room_number"].tolist(),
        )

        if st.button(
            "🗑️ Xóa phòng",
            type="secondary",
        ):

            try:

                execute(
                    """
                    DELETE FROM rooms
                    WHERE room_number=%s
                    """,
                    (delete_room,),
                )

                # Xóa dữ liệu phụ liên quan đến phòng
                execute(
                    """
                    DELETE FROM minibar
                    WHERE room_number=%s
                    """,
                    (delete_room,),
                )

                execute(
                    """
                    DELETE FROM housekeeping
                    WHERE room_number=%s
                    """,
                    (delete_room,),
                )

                st.success(
                    f"Đã xóa phòng {delete_room}"
                )

                st.rerun()

            except Error as e:

                st.error(
                    "❌ Không thể xóa phòng."
                )
                st.code(str(e))


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏨 Hotel Manager v2.0 - MySQL Aiven"
)

st.sidebar.caption(
    "Quản lý phòng • Khách • Buồng phòng • Minibar • Doanh thu"
)
