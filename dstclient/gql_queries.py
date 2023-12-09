#
# Copyright 2023 Basislager Services
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

"""GraphQL queries used in the WebAPI class.

Functions defined here return a tuple (query, params) ready for execution with
the gql library.
"""


from typing import Any, SupportsInt

from gql import gql

from graphql.language.ast import DocumentNode


QueryType = tuple[DocumentNode, dict[str, Any]]


# TODO: Require the URL instead of the ID as parameter to match JS requests
#       on the website?
def get_forum_info(article_id: int) -> QueryType:
    """Get basic information for a forum."""
    query = gql(
        """
        query GetForumInfo ($contextUri: String!) {
            getForumByContextUri (contextUri: $contextUri) {
                id
            }
        }
        """
    )
    params = {"contextUri": f"https://www.derstandard.at/story/{article_id}"}
    return query, params


def legacy_profile_public(legacy_id: SupportsInt) -> QueryType:
    """Get profile information from a legacy profile ID."""
    legacy_id = int(legacy_id)
    query = gql(
        """
        query LegacyProfilePublic ($legacyMemberId: ID) {
            getCommunityMemberPublic (legacyMemberId: $legacyMemberId) {
                name
                memberId
                memberCreatedAt
            }
        }
        """
    )
    params = {"legacyMemberId": legacy_id}
    return query, params


def member_relationships_public(member_id: str) -> QueryType:
    """Get member relationships for a user."""
    query = gql(
        """
        query MemberRelationshipsPublic ($memberId: ID!) {
            getMemberRelationshipsPublic (memberId: $memberId) {
                follower {
                    member {
                        legacyId
                        memberId
                        name
                        memberCreatedAt
                    }
                }
                followees {
                    member {
                        legacyId
                        memberId
                        name
                        memberCreatedAt
                    }
                }
            }
        }
        """
    )
    params = {"memberId": member_id}
    return query, params


def threads_by_forum_query(forum_id: str, next_cursor: str | None = None) -> QueryType:
    """Get a page of threads in a forum."""
    query = gql(
        """
        fragment PostingInfo on Posting {
          id
          author {
            legacyData {
              legacyCommunityIdentity
            }
          }
          legacy {
            postingId
          }
          title
          text
          history {
            created
          }
          reactions {
            aggregated {
              name
              value
              statistic
            }
          }
        }

        query ThreadsByForumQuery($id: String!, $nextCursor: String) {
          getForumRootPostingsV2(
            getForumRootPostingsParamsV2: {
              forumId: $id
              sortOrder: ByTime
              first: Max
              after: $nextCursor
            }
          ) {
            pageInfo {
              nextCursor
              hasNextPage
            }
            edges {
              node {
                ...PostingInfo
                replies {
                  ...PostingInfo
                  replies {
                    ...PostingInfo
                    replies {
                      ...PostingInfo
                      replies {
                        ...PostingInfo
                        replies {
                          ...PostingInfo
                          replies {
                            ...PostingInfo
                            replies {
                              ...PostingInfo
                              replies {
                                ...PostingInfo
                                replies {
                                  ...PostingInfo
                                  replies {
                                    ...PostingInfo
                                    replies {
                                      ...PostingInfo
                                      replies {
                                        ...PostingInfo
                                        replies {
                                          ...PostingInfo
                                          replies {
                                            ...PostingInfo
                                            replies {
                                              ...PostingInfo
                                              replies {
                                                ...PostingInfo
                                                replies {
                                                  ...PostingInfo
                                                  replies {
                                                    ...PostingInfo
                                                    replies {
                                                      ...PostingInfo
                                                      replies {
                                                        ...PostingInfo
                                                        replies {
                                                          ...PostingInfo
                                                          replies {
                                                            ...PostingInfo
                                                            replies {
                                                              ...PostingInfo
                                                              replies {
                                                                ...PostingInfo
                                                                replies {
                                                                  ...PostingInfo
                                                                  replies {
                                                                    ...PostingInfo
                                                                    replies {
                                                                      ...PostingInfo
                                                                      replies {
                                                                        ...PostingInfo
                                                                        replies {
                                                                          ...PostingInfo
                                                                          replies {
                                                                            ...PostingInfo
                                                                            replies {
                                                                              ...PostingInfo
                                                                            }
                                                                          }
                                                                        }
                                                                      }
                                                                    }
                                                                  }
                                                                }
                                                              }
                                                            }
                                                          }
                                                        }
                                                      }
                                                    }
                                                  }
                                                }
                                              }
                                            }
                                          }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
              cursor
            }
          }
        }
        """
    )
    params = {"id": forum_id, "nextCursor": next_cursor if next_cursor else ""}
    return query, params
