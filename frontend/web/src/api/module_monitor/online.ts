import { request } from "@utils";
const API_PATH = "/monitor/online";
const OnlineAPI = {
  listCurrentOnline() {
    return request<ApiResponse<OnlineUserTable[]>>({
      url: `${API_PATH}/current`,
      method: "get",
    });
  },
};
export default OnlineAPI;

export interface OnlineUserPageQuery extends PageQuery, UserByQueryParams {
  ipaddr?: string;
  name?: string;
  login_location?: string;
}

export interface OnlineUserTable {
  session_id: string;
  user_id: number;
  is_superuser?: boolean;
  name: string;
  user_name: string;
  ipaddr?: string;
  login_location?: string;
  os?: string;
  browser?: string;
  login_time?: string;
  login_type?: string;
}
